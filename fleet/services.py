from __future__ import annotations

from datetime import date

from django.db import transaction
from django.db.models import F, Q

from audit.services import log_action
from fleet.models import Car


def service_due_filter(*, today: date):
    return Q(next_service_date__isnull=False, next_service_date__lte=today) | Q(
        next_service_mileage__isnull=False,
        current_mileage__gte=F("next_service_mileage"),
    )


def car_service_due_reasons(car: Car, *, today: date | None = None) -> list[str]:
    today = today or date.today()
    reasons = []
    if car.next_service_date and car.next_service_date <= today:
        reasons.append(f"дата ТО {car.next_service_date:%d.%m.%Y}")
    if (
        car.next_service_mileage is not None
        and car.current_mileage >= car.next_service_mileage
    ):
        reasons.append(
            f"пробег {car.current_mileage} км достиг лимита {car.next_service_mileage} км"
        )
    return reasons


def car_is_service_due(car: Car, *, today: date | None = None) -> bool:
    return bool(car_service_due_reasons(car, today=today))


def cars_due_for_service(*, today: date | None = None):
    today = today or date.today()
    return Car.objects.filter(service_due_filter(today=today))


def update_car_mileage(*, car: Car, mileage: int | None) -> bool:
    if mileage is None or mileage <= car.current_mileage:
        return False
    car.current_mileage = mileage
    car.save(update_fields=["current_mileage", "updated_at"])
    return True


def mark_car_for_maintenance_if_due(
    *,
    car: Car,
    actor=None,
    today: date | None = None,
    payload_extra: dict | None = None,
) -> bool:
    today = today or date.today()
    reasons = car_service_due_reasons(car, today=today)
    if not reasons:
        return False

    status_changed = False
    if car.status == Car.Status.AVAILABLE:
        car.status = Car.Status.MAINTENANCE
        car.save(update_fields=["status", "updated_at"])
        status_changed = True

    payload = {
        "reasons": reasons,
        "status_changed": status_changed,
        "car_status": car.status,
    }
    if payload_extra:
        payload.update(payload_extra)
    log_action(
        actor=actor,
        action="car.maintenance_due",
        obj=car,
        payload=payload,
    )
    return status_changed


@transaction.atomic
def mark_due_cars_for_maintenance(*, actor=None, today: date | None = None) -> int:
    today = today or date.today()
    count = 0
    cars = (
        cars_due_for_service(today=today)
        .select_for_update()
        .filter(status=Car.Status.AVAILABLE)
    )
    for car in cars:
        if mark_car_for_maintenance_if_due(car=car, actor=actor, today=today):
            count += 1
    return count
