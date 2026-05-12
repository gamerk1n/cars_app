from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db import transaction
from django.db.models import Exists, F, OuterRef, Q
from django.utils import timezone

from audit.services import log_action
from fleet.models import Car, MaintenanceRecord
from fleet.services import car_service_due_reasons, update_car_mileage
from reports.models import Report
from requests.models import Reservation, Request, VehicleInspection, VehicleInspectionPhoto
from requests.notifications import notify_request_event


class RequestServiceError(Exception):
    pass


REQUEST_OPEN_STATUSES = [
    Request.Status.PENDING,
    Request.Status.APPROVED,
    Request.Status.OVERDUE,
]

DAMAGE_ZONE_LABELS = dict(VehicleInspection.DAMAGE_ZONE_CHOICES)


@dataclass(frozen=True)
class AutoApprovalDecision:
    approved: bool
    reasons: list[str]


def assignment_conflicts_for_request(*, req: Request):
    return Reservation.objects.filter(
        car_id=OuterRef("pk"),
        status=Reservation.Status.ACTIVE,
        start_date__lte=req.end_date,
        end_date__gte=req.start_date,
    ).exclude(request_id=req.pk)


def available_cars_for_request(req: Request):
    conflicts = assignment_conflicts_for_request(req=req)
    return (
        Car.objects.exclude(status=Car.Status.MAINTENANCE)
        .annotate(has_assignment_conflict=Exists(conflicts))
        .filter(has_assignment_conflict=False)
        .exclude(
            Q(next_service_date__isnull=False, next_service_date__lte=req.start_date)
            | Q(
                next_service_mileage__isnull=False,
                current_mileage__gte=F("next_service_mileage"),
            )
        )
        .order_by("brand_model", "vin", "id")
    )


def car_has_assignment_conflict(*, req: Request, car: Car) -> bool:
    return (
        Reservation.objects.filter(
            car=car,
            status=Reservation.Status.ACTIVE,
            start_date__lte=req.end_date,
            end_date__gte=req.start_date,
        )
        .exclude(request_id=req.pk)
        .exists()
    )


def sync_car_status_from_reservations(*, car: Car, today=None) -> Car:
    if car.status == Car.Status.MAINTENANCE:
        return car
    today = today or timezone.localdate()
    has_current_reservation = Reservation.objects.filter(
        car=car,
        status=Reservation.Status.ACTIVE,
        start_date__lte=today,
        end_date__gte=today,
    ).exists()
    new_status = Car.Status.ASSIGNED if has_current_reservation else Car.Status.AVAILABLE
    if car.status != new_status:
        car.status = new_status
        car.save(update_fields=["status", "updated_at"])
    return car


def create_or_update_reservation(*, req: Request, car: Car, actor) -> Reservation:
    reservation, _created = Reservation.objects.update_or_create(
        request=req,
        defaults={
            "car": car,
            "employee": req.employee,
            "start_date": req.start_date,
            "end_date": req.end_date,
            "status": Reservation.Status.ACTIVE,
            "created_by": actor if getattr(actor, "is_authenticated", False) else None,
            "cancelled_at": None,
            "completed_at": None,
        },
    )
    sync_car_status_from_reservations(car=car)
    return reservation


def cancel_request_reservation(*, req: Request, actor) -> None:
    try:
        reservation = req.reservation
    except Reservation.DoesNotExist:
        return
    if reservation.status != Reservation.Status.ACTIVE:
        return
    reservation.status = Reservation.Status.CANCELLED
    reservation.cancelled_at = timezone.now()
    reservation.save(update_fields=["status", "cancelled_at", "updated_at"])
    sync_car_status_from_reservations(car=reservation.car)
    log_action(
        actor=actor,
        action="request.reservation_cancel",
        obj=req,
        payload={"reservation_id": reservation.id, "car_id": reservation.car_id},
    )


def complete_request_reservation(*, req: Request, actor) -> None:
    try:
        reservation = req.reservation
    except Reservation.DoesNotExist:
        return
    if reservation.status != Reservation.Status.ACTIVE:
        return
    reservation.status = Reservation.Status.COMPLETED
    reservation.completed_at = timezone.now()
    reservation.save(update_fields=["status", "completed_at", "updated_at"])
    log_action(
        actor=actor,
        action="request.reservation_complete",
        obj=req,
        payload={"reservation_id": reservation.id, "car_id": reservation.car_id},
    )


def _damage_zone_labels(zones: list[str]) -> list[str]:
    return [DAMAGE_ZONE_LABELS.get(zone, zone) for zone in zones]


def inspection_defects_summary(inspection: VehicleInspection) -> str:
    parts = []
    defects = (inspection.defects or "").strip()
    if defects:
        parts.append(defects)
    zones = _damage_zone_labels(inspection.damage_zones or [])
    if zones:
        parts.append("Зоны повреждений: " + ", ".join(zones))
    return "\n".join(parts).strip()


def employee_has_open_request_conflict(*, req: Request) -> bool:
    return (
        Request.objects.filter(
            employee=req.employee,
            status__in=REQUEST_OPEN_STATUSES,
            start_date__lte=req.end_date,
            end_date__gte=req.start_date,
        )
        .exclude(pk=req.pk)
        .exists()
    )


def request_duration_days(req: Request) -> int:
    return (req.end_date - req.start_date).days + 1


def reason_matches_auto_approval_rules(req: Request) -> bool:
    keywords = getattr(settings, "REQUEST_AUTO_APPROVAL_REASON_KEYWORDS", [])
    if not keywords:
        return True
    reason = (req.reason or "").casefold()
    return any(keyword.casefold() in reason for keyword in keywords)


def evaluate_auto_approval(req: Request) -> AutoApprovalDecision:
    reasons = []
    today = timezone.localdate()
    max_days = getattr(settings, "REQUEST_AUTO_APPROVAL_MAX_DAYS", 14)

    if req.status != Request.Status.PENDING:
        reasons.append("заявка не находится в статусе ожидания")
    if not req.employee.user.is_active:
        reasons.append("сотрудник неактивен")
    if not req.rules_accepted:
        reasons.append("сотрудник не подтвердил правила")
    if req.start_date < today:
        reasons.append("дата начала уже прошла")
    if req.start_date > req.end_date:
        reasons.append("дата окончания раньше даты начала")
    if request_duration_days(req) > max_days:
        reasons.append(f"срок заявки больше {max_days} дней")
    if not reason_matches_auto_approval_rules(req):
        reasons.append("причина не подходит под правила автоодобрения")
    if employee_has_open_request_conflict(req=req):
        reasons.append("у сотрудника уже есть заявка на пересекающийся период")
    if not available_cars_for_request(req).exists():
        reasons.append("нет доступных автомобилей на период заявки")

    return AutoApprovalDecision(approved=not reasons, reasons=reasons)


@transaction.atomic
def set_pending(*, req: Request, actor) -> Request:
    cancel_request_reservation(req=req, actor=actor)
    req.status = Request.Status.PENDING
    req.car = None
    req.assigned_at = None
    req.save(update_fields=["status", "car", "assigned_at", "updated_at"])
    log_action(actor=actor, action="request.set_pending", obj=req)
    return req


@transaction.atomic
def approve_request(*, req: Request, actor) -> Request:
    if req.status == Request.Status.COMPLETED:
        raise RequestServiceError("Нельзя одобрить завершённую заявку.")
    req.status = Request.Status.APPROVED
    req.save(update_fields=["status", "updated_at"])
    log_action(actor=actor, action="request.approve", obj=req)
    notify_request_event("approved", req, actor=actor)
    return req


@transaction.atomic
def reject_request(*, req: Request, actor, reason: str | None = None) -> Request:
    if req.status == Request.Status.COMPLETED:
        raise RequestServiceError("Нельзя отклонить завершённую заявку.")
    cancel_request_reservation(req=req, actor=actor)
    req.status = Request.Status.REJECTED
    req.car = None
    req.assigned_at = None
    req.save(update_fields=["status", "car", "assigned_at", "updated_at"])
    log_action(
        actor=actor,
        action="request.reject",
        obj=req,
        payload={"reason": reason} if reason else {},
    )
    notify_request_event("rejected", req, actor=actor, extra={"reason": reason})
    return req


@transaction.atomic
def assign_car(*, req: Request, car: Car, actor) -> Request:
    car = Car.objects.select_for_update().get(pk=car.pk)
    if req.status != Request.Status.APPROVED:
        raise RequestServiceError("Автомобиль можно назначить только одобренной заявке.")
    if req.car_id:
        raise RequestServiceError("На заявку уже назначен автомобиль.")
    if car.status == Car.Status.MAINTENANCE:
        raise RequestServiceError("Автомобиль находится на обслуживании.")
    due_reasons = car_service_due_reasons(car, today=req.start_date)
    if due_reasons:
        raise RequestServiceError("Автомобиль требует ТО: " + "; ".join(due_reasons))

    if car_has_assignment_conflict(req=req, car=car):
        raise RequestServiceError("У автомобиля уже есть назначение на пересекающийся период.")

    req.car = car
    req.assigned_at = timezone.now()
    req.save(update_fields=["car", "assigned_at", "updated_at"])

    reservation = create_or_update_reservation(req=req, car=car, actor=actor)

    log_action(
        actor=actor,
        action="request.assign_car",
        obj=req,
        payload={"car_id": car.id, "reservation_id": reservation.id},
    )
    notify_request_event("assigned", req, actor=actor)
    return req


@transaction.atomic
def auto_assign_car(*, req: Request, actor) -> Request:
    if req.status != Request.Status.APPROVED:
        raise RequestServiceError("Автоназначение доступно только для одобренных заявок.")
    if req.car_id:
        raise RequestServiceError("На заявку уже назначен автомобиль.")

    car = available_cars_for_request(req).select_for_update().first()
    if car is None:
        raise RequestServiceError("Нет доступных автомобилей на период заявки.")

    req = assign_car(req=req, car=car, actor=actor)
    log_action(
        actor=actor,
        action="request.auto_assign_car",
        obj=req,
        payload={"car_id": car.id},
    )
    return req


@transaction.atomic
def process_auto_approval(*, req: Request, actor) -> tuple[Request, AutoApprovalDecision]:
    req = Request.objects.select_related("employee__user").select_for_update().get(pk=req.pk)
    decision = evaluate_auto_approval(req)
    if not decision.approved:
        log_action(
            actor=actor,
            action="request.auto_approval_blocked",
            obj=req,
            payload={"reasons": decision.reasons},
        )
        notify_request_event(
            "auto_approval_blocked",
            req,
            actor=actor,
            extra={"reasons": decision.reasons},
        )
        return req, decision

    approve_request(req=req, actor=actor)
    auto_assign_car(req=req, actor=actor)
    req.refresh_from_db()
    log_action(
        actor=actor,
        action="request.auto_approve",
        obj=req,
        payload={"car_id": req.car_id},
    )
    return req, decision


@transaction.atomic
def create_vehicle_inspection(
    *,
    req: Request,
    kind: str,
    actor,
    data: dict,
    photo_files: list[tuple[str, object | None]] | None = None,
) -> VehicleInspection:
    req = Request.objects.select_related("employee").select_for_update().get(pk=req.pk)
    if not req.car_id:
        raise RequestServiceError("Нельзя создать акт осмотра без назначенного автомобиля.")
    if kind == VehicleInspection.Kind.ISSUE and req.status != Request.Status.APPROVED:
        raise RequestServiceError("Акт выдачи можно создать только для одобренной заявки.")
    if kind == VehicleInspection.Kind.RETURN and req.status not in [
        Request.Status.APPROVED,
        Request.Status.OVERDUE,
    ]:
        raise RequestServiceError("Акт возврата можно создать только для выданной заявки.")

    try:
        inspection = VehicleInspection.objects.create(
            request=req,
            car=req.car,
            employee=req.employee,
            kind=kind,
            mileage=data["mileage"],
            fuel_level=data["fuel_level"],
            exterior_condition=data.get("exterior_condition", ""),
            interior_condition=data.get("interior_condition", ""),
            damage_zones=data.get("damage_zones", []),
            defects=data.get("defects", ""),
            employee_signature=data["employee_signature"],
            inspector_signature=data["inspector_signature"],
            created_by=actor if getattr(actor, "is_authenticated", False) else None,
        )
    except IntegrityError as exc:
        raise RequestServiceError("Акт этого типа для заявки уже создан.") from exc

    for label, photo in photo_files or []:
        if not photo:
            continue
        VehicleInspectionPhoto.objects.create(
            inspection=inspection,
            label=label,
            image=photo,
            original_name=Path(photo.name).name,
        )

    log_action(
        actor=actor,
        action=f"request.inspection.{kind}",
        obj=req,
        payload={"inspection_id": inspection.id, "photo_count": inspection.photos.count()},
    )
    update_car_mileage(car=req.car, mileage=inspection.mileage)
    return inspection


@transaction.atomic
def complete_request_with_inspection(
    *,
    req: Request,
    actor,
    inspection_data: dict,
    photo_files: list[tuple[str, object | None]] | None = None,
) -> tuple[Request, VehicleInspection]:
    inspection = create_vehicle_inspection(
        req=req,
        kind=VehicleInspection.Kind.RETURN,
        actor=actor,
        data=inspection_data,
        photo_files=photo_files,
    )
    req = complete_request(
        req=req,
        actor=actor,
        defects=inspection_defects_summary(inspection),
    )
    return req, inspection


@transaction.atomic
def complete_request(*, req: Request, actor, defects: str | None = None) -> Request:
    if req.status not in [Request.Status.APPROVED, Request.Status.OVERDUE]:
        raise RequestServiceError("Завершить можно только одобренную или просроченную заявку.")
    if not req.car_id:
        raise RequestServiceError("Нельзя завершить заявку без назначенного автомобиля.")

    car = Car.objects.select_for_update().get(pk=req.car_id)

    normalized_defects = (defects or "").strip()

    req.status = Request.Status.COMPLETED
    req.returned_at = timezone.now()
    req.return_defects = normalized_defects
    req.save(update_fields=["status", "returned_at", "return_defects", "updated_at"])

    car.status = Car.Status.MAINTENANCE if normalized_defects else Car.Status.AVAILABLE
    car.save(update_fields=["status", "updated_at"])

    if normalized_defects:
        MaintenanceRecord.objects.create(
            car=car,
            request=req,
            kind=MaintenanceRecord.Kind.REPAIR,
            service_date=timezone.localdate(),
            title=f"Дефекты после возврата по заявке #{req.id}",
            description=normalized_defects,
            created_by=actor,
        )

    complete_request_reservation(req=req, actor=actor)

    report = Report.objects.create(
        name=f"Отчёт по заявке #{req.id}",
        request=req,
        car=car,
        employee=req.employee,
        start_date=req.start_date,
        end_date=req.end_date,
    )

    log_action(actor=actor, action="request.complete", obj=req, payload={"report_id": report.id, "car_status": car.status})
    sync_car_status_from_reservations(car=car)
    notify_request_event("completed", req, actor=actor)
    if normalized_defects:
        notify_request_event(
            "defects_reported",
            req,
            actor=actor,
            extra={"defects": normalized_defects},
        )
    return req


def validate_request(req: Request) -> None:
    try:
        req.full_clean()
    except ValidationError as e:
        raise RequestServiceError(str(e)) from e
