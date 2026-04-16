from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from audit.services import log_action
from fleet.models import Car
from reports.models import Report
from requests.models import Request


class RequestServiceError(Exception):
    pass


@transaction.atomic
def set_pending(*, req: Request, actor) -> Request:
    req.status = Request.Status.PENDING
    req.save(update_fields=["status", "updated_at"])
    log_action(actor=actor, action="request.set_pending", obj=req)
    return req


@transaction.atomic
def approve_request(*, req: Request, actor) -> Request:
    if req.status == Request.Status.COMPLETED:
        raise RequestServiceError("Нельзя одобрить завершённую заявку.")
    req.status = Request.Status.APPROVED
    req.save(update_fields=["status", "updated_at"])
    log_action(actor=actor, action="request.approve", obj=req)
    return req


@transaction.atomic
def reject_request(*, req: Request, actor, reason: str | None = None) -> Request:
    if req.status == Request.Status.COMPLETED:
        raise RequestServiceError("Нельзя отклонить завершённую заявку.")
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
    return req


@transaction.atomic
def assign_car(*, req: Request, car: Car, actor) -> Request:
    if req.status != Request.Status.APPROVED:
        raise RequestServiceError("Автомобиль можно назначить только одобренной заявке.")
    if req.car_id:
        raise RequestServiceError("На заявку уже назначен автомобиль.")
    if car.status != Car.Status.AVAILABLE:
        raise RequestServiceError("Автомобиль недоступен для выдачи.")

    car.status = Car.Status.ASSIGNED
    car.save(update_fields=["status", "updated_at"])

    req.car = car
    req.assigned_at = timezone.now()
    req.save(update_fields=["car", "assigned_at", "updated_at"])

    log_action(actor=actor, action="request.assign_car", obj=req, payload={"car_id": car.id})
    return req


@transaction.atomic
def complete_request(*, req: Request, actor, defects: str | None = None) -> Request:
    if req.status != Request.Status.APPROVED:
        raise RequestServiceError("Завершить можно только одобренную заявку.")
    if not req.car_id:
        raise RequestServiceError("Нельзя завершить заявку без назначенного автомобиля.")

    car = Car.objects.select_for_update().get(pk=req.car_id)

    req.status = Request.Status.COMPLETED
    req.returned_at = timezone.now()
    req.return_defects = (defects or "").strip()
    req.save(update_fields=["status", "returned_at", "return_defects", "updated_at"])

    car.status = Car.Status.AVAILABLE
    car.save(update_fields=["status", "updated_at"])

    report = Report.objects.create(
        name=f"Отчёт по заявке #{req.id}",
        request=req,
        car=car,
        employee=req.employee,
        start_date=req.start_date,
        end_date=req.end_date,
    )

    log_action(actor=actor, action="request.complete", obj=req, payload={"report_id": report.id})
    return req


def validate_request(req: Request) -> None:
    try:
        req.full_clean()
    except ValidationError as e:
        raise RequestServiceError(str(e)) from e
