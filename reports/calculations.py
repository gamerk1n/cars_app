from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from typing import Iterable

from django.utils import timezone

from reports.models import Report
from requests.models import VehicleInspection


ONE_DECIMAL = Decimal("0.1")


@dataclass(frozen=True)
class ReportUsageCalculation:
    usage_days: int
    overdue_days: int
    issue_mileage: int | None
    return_mileage: int | None
    mileage_delta: int | None
    average_daily_mileage: Decimal | None
    mileage_until_service: int | None
    service_forecast_days: int | None
    service_forecast_date: date | None


@dataclass(frozen=True)
class CarUtilizationRow:
    car_id: int
    brand_model: str
    vin: str
    busy_days: int
    utilization_percent: Decimal


@dataclass(frozen=True)
class FleetMetrics:
    period_start: date
    period_end: date
    period_days: int
    total_cars: int
    report_count: int
    busy_car_days: int
    available_car_days: int
    idle_car_days: int
    utilization_percent: Decimal
    average_request_days: Decimal
    total_mileage: int | None
    average_daily_mileage: Decimal | None
    overdue_count: int
    average_overdue_days: Decimal
    max_overdue_days: int
    top_cars_by_utilization: list[CarUtilizationRow]


def inclusive_days(start: date, end: date) -> int:
    if end < start:
        return 0
    return (end - start).days + 1


def overlap_days(
    start: date,
    end: date,
    period_start: date,
    period_end: date,
) -> int:
    return inclusive_days(max(start, period_start), min(end, period_end))


def calculate_report_usage(
    report: Report,
    *,
    today: date | None = None,
) -> ReportUsageCalculation:
    today = today or timezone.localdate()
    issue_inspection = _inspection_by_kind(report, VehicleInspection.Kind.ISSUE)
    return_inspection = _inspection_by_kind(report, VehicleInspection.Kind.RETURN)
    issue_mileage = issue_inspection.mileage if issue_inspection else None
    return_mileage = return_inspection.mileage if return_inspection else None
    usage_days = inclusive_days(report.start_date, report.end_date)
    overdue_days = _overdue_days(report)
    mileage_delta = _mileage_delta(issue_mileage, return_mileage)
    average_daily_mileage = _average(mileage_delta, usage_days)
    mileage_until_service = _mileage_until_service(report)
    service_forecast_days = _service_forecast_days(
        mileage_until_service,
        average_daily_mileage,
    )
    service_forecast_date = (
        today + timedelta(days=service_forecast_days)
        if service_forecast_days is not None
        else None
    )
    return ReportUsageCalculation(
        usage_days=usage_days,
        overdue_days=overdue_days,
        issue_mileage=issue_mileage,
        return_mileage=return_mileage,
        mileage_delta=mileage_delta,
        average_daily_mileage=average_daily_mileage,
        mileage_until_service=mileage_until_service,
        service_forecast_days=service_forecast_days,
        service_forecast_date=service_forecast_date,
    )


def calculate_fleet_metrics(
    reports: Iterable[Report],
    *,
    total_cars: int,
    period_start: date | None = None,
    period_end: date | None = None,
    today: date | None = None,
) -> FleetMetrics:
    today = today or timezone.localdate()
    reports = list(reports)
    period_start, period_end = _resolve_period(
        reports=reports,
        period_start=period_start,
        period_end=period_end,
        today=today,
    )
    period_days = inclusive_days(period_start, period_end)
    available_car_days = period_days * total_cars

    busy_car_days = 0
    total_request_days = 0
    total_mileage = 0
    mileage_days = 0
    mileage_found = False
    overdue_days: list[int] = []
    per_car: dict[int, dict[str, object]] = {}

    for report in reports:
        report_busy_days = overlap_days(
            report.start_date,
            report.end_date,
            period_start,
            period_end,
        )
        busy_car_days += report_busy_days
        total_request_days += inclusive_days(report.start_date, report.end_date)
        overdue = _overdue_days(report)
        if overdue:
            overdue_days.append(overdue)

        calculation = calculate_report_usage(report, today=today)
        if calculation.mileage_delta is not None:
            total_mileage += calculation.mileage_delta
            mileage_days += calculation.usage_days
            mileage_found = True

        car_stats = per_car.setdefault(
            report.car_id,
            {
                "brand_model": report.car.brand_model,
                "vin": report.car.vin,
                "busy_days": 0,
            },
        )
        car_stats["busy_days"] = int(car_stats["busy_days"]) + report_busy_days

    idle_car_days = max(available_car_days - busy_car_days, 0)
    top_cars = [
        CarUtilizationRow(
            car_id=car_id,
            brand_model=str(stats["brand_model"]),
            vin=str(stats["vin"]),
            busy_days=int(stats["busy_days"]),
            utilization_percent=_percent(int(stats["busy_days"]), period_days),
        )
        for car_id, stats in per_car.items()
    ]
    top_cars.sort(key=lambda row: (-row.utilization_percent, row.brand_model, row.vin))

    return FleetMetrics(
        period_start=period_start,
        period_end=period_end,
        period_days=period_days,
        total_cars=total_cars,
        report_count=len(reports),
        busy_car_days=busy_car_days,
        available_car_days=available_car_days,
        idle_car_days=idle_car_days,
        utilization_percent=_percent(busy_car_days, available_car_days),
        average_request_days=_average(total_request_days, len(reports)) or Decimal("0.0"),
        total_mileage=total_mileage if mileage_found else None,
        average_daily_mileage=_average(total_mileage, mileage_days),
        overdue_count=len(overdue_days),
        average_overdue_days=_average(sum(overdue_days), len(overdue_days))
        or Decimal("0.0"),
        max_overdue_days=max(overdue_days, default=0),
        top_cars_by_utilization=top_cars[:5],
    )


def _inspection_by_kind(report: Report, kind: str) -> VehicleInspection | None:
    inspections = getattr(report.request, "_prefetched_objects_cache", {}).get(
        "inspections"
    )
    if inspections is None:
        inspections = report.request.inspections.all()
    for inspection in inspections:
        if inspection.kind == kind:
            return inspection
    return None


def _overdue_days(report: Report) -> int:
    returned_at = report.request.returned_at
    if not returned_at:
        return 0
    return max((returned_at.date() - report.end_date).days, 0)


def _mileage_delta(
    issue_mileage: int | None,
    return_mileage: int | None,
) -> int | None:
    if issue_mileage is None or return_mileage is None:
        return None
    return max(return_mileage - issue_mileage, 0)


def _mileage_until_service(report: Report) -> int | None:
    if report.car.next_service_mileage is None:
        return None
    return max(report.car.next_service_mileage - report.car.current_mileage, 0)


def _service_forecast_days(
    mileage_until_service: int | None,
    average_daily_mileage: Decimal | None,
) -> int | None:
    if mileage_until_service is None or average_daily_mileage in [None, Decimal("0.0")]:
        return None
    return int(
        (Decimal(mileage_until_service) / average_daily_mileage).to_integral_value(
            rounding=ROUND_CEILING
        )
    )


def _average(value: int | None, count: int) -> Decimal | None:
    if value is None or count <= 0:
        return None
    return (Decimal(value) / Decimal(count)).quantize(ONE_DECIMAL, rounding=ROUND_HALF_UP)


def _percent(part: int, total: int) -> Decimal:
    if total <= 0:
        return Decimal("0.0")
    return ((Decimal(part) * Decimal(100)) / Decimal(total)).quantize(
        ONE_DECIMAL,
        rounding=ROUND_HALF_UP,
    )


def _resolve_period(
    *,
    reports: list[Report],
    period_start: date | None,
    period_end: date | None,
    today: date,
) -> tuple[date, date]:
    if period_start is None:
        period_start = min((report.start_date for report in reports), default=today)
    if period_end is None:
        period_end = max((report.end_date for report in reports), default=today)
    if period_end < period_start:
        return period_end, period_start
    return period_start, period_end
