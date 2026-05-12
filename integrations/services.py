from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from audit.services import log_action
from fleet.models import Car
from fleet.services import mark_car_for_maintenance_if_due, update_car_mileage
from integrations.models import TelematicsReading


@dataclass(frozen=True)
class TelematicsIngestResult:
    car_id: int
    vin: str
    previous_mileage: int
    mileage: int
    accepted: bool
    ignored_reason: str
    maintenance_marked: bool
    car_status: str
    reading_id: int


@transaction.atomic
def ingest_telematics_mileage(
    *,
    vin: str,
    mileage: int,
    recorded_at=None,
    source: str = "",
    external_event_id: str = "",
) -> TelematicsIngestResult:
    normalized_vin = vin.strip().upper()
    recorded_at = recorded_at or timezone.now()
    car = Car.objects.select_for_update().get(vin=normalized_vin)
    previous_mileage = car.current_mileage
    accepted = mileage > previous_mileage
    ignored_reason = "" if accepted else "Пробег не больше текущего значения"

    reading = TelematicsReading.objects.create(
        car=car,
        vin=normalized_vin,
        mileage=mileage,
        recorded_at=recorded_at,
        source=source.strip(),
        external_event_id=external_event_id.strip(),
        accepted=accepted,
        ignored_reason=ignored_reason,
    )

    maintenance_marked = False
    if accepted:
        update_car_mileage(car=car, mileage=mileage)
        log_action(
            actor=None,
            action="car.telematics_mileage",
            obj=car,
            payload={
                "previous_mileage": previous_mileage,
                "mileage": mileage,
                "reading_id": reading.id,
                "source": source,
                "external_event_id": external_event_id,
            },
        )
        maintenance_marked = mark_car_for_maintenance_if_due(
            car=car,
            actor=None,
            payload_extra={
                "trigger": "telematics",
                "reading_id": reading.id,
                "source": source,
            },
        )
    else:
        log_action(
            actor=None,
            action="car.telematics_mileage_ignored",
            obj=car,
            payload={
                "current_mileage": previous_mileage,
                "mileage": mileage,
                "reading_id": reading.id,
                "source": source,
                "external_event_id": external_event_id,
                "reason": ignored_reason,
            },
        )

    car.refresh_from_db(fields=["status", "current_mileage"])
    return TelematicsIngestResult(
        car_id=car.id,
        vin=car.vin,
        previous_mileage=previous_mileage,
        mileage=mileage,
        accepted=accepted,
        ignored_reason=ignored_reason,
        maintenance_marked=maintenance_marked,
        car_status=car.status,
        reading_id=reading.id,
    )
