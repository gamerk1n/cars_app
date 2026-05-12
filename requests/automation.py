from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from audit.models import ActionLog
from audit.services import log_action
from fleet.services import mark_due_cars_for_maintenance
from requests.models import Request
from requests.notifications import notify_request_event
from requests.services import RequestServiceError, auto_assign_car


@dataclass
class AutomationSummary:
    overdue_marked: int = 0
    return_reminders_created: int = 0
    auto_assigned: int = 0
    auto_assign_blocked: int = 0
    stale_pending_flagged: int = 0
    maintenance_due_marked: int = 0

    def as_dict(self):
        return asdict(self)


def _log_exists_today(*, action: str, req: Request, today: date) -> bool:
    return ActionLog.objects.filter(
        action=action,
        object_type=req._meta.label_lower,
        object_id=str(req.pk),
        created_at__date=today,
    ).exists()


def _log_once_per_day(*, actor, action: str, req: Request, today: date, payload: dict) -> bool:
    if _log_exists_today(action=action, req=req, today=today):
        return False
    log_action(actor=actor, action=action, obj=req, payload=payload)
    return True


@transaction.atomic
def mark_overdue_returns(*, actor=None, today: date | None = None) -> int:
    today = today or timezone.localdate()
    count = 0
    qs = (
        Request.objects.select_for_update()
        .filter(
            status=Request.Status.APPROVED,
            car__isnull=False,
            returned_at__isnull=True,
            end_date__lt=today,
        )
        .select_related("car", "employee")
    )
    for req in qs:
        req.status = Request.Status.OVERDUE
        req.save(update_fields=["status", "updated_at"])
        log_action(
            actor=actor,
            action="request.return_overdue",
            obj=req,
            payload={"due_date": req.end_date.isoformat(), "car_id": req.car_id},
        )
        notify_request_event("return_overdue", req, actor=actor)
        count += 1
    return count


def create_return_reminders(*, actor=None, today: date | None = None) -> int:
    today = today or timezone.localdate()
    reminder_days = getattr(settings, "REQUEST_RETURN_REMINDER_DAYS", 1)
    reminder_until = today + timedelta(days=reminder_days)
    count = 0
    qs = Request.objects.filter(
        status=Request.Status.APPROVED,
        car__isnull=False,
        returned_at__isnull=True,
        end_date__gte=today,
        end_date__lte=reminder_until,
    ).select_related("car", "employee")
    for req in qs:
        created = _log_once_per_day(
            actor=actor,
            action="request.return_due_soon",
            req=req,
            today=today,
            payload={
                "due_date": req.end_date.isoformat(),
                "days_until_due": (req.end_date - today).days,
                "car_id": req.car_id,
            },
        )
        if created:
            notify_request_event("return_due_soon", req, actor=actor)
            count += 1
    return count


def retry_auto_assignment(*, actor=None, today: date | None = None) -> tuple[int, int]:
    today = today or timezone.localdate()
    assigned = 0
    blocked = 0
    qs = Request.objects.filter(
        status=Request.Status.APPROVED,
        car__isnull=True,
        end_date__gte=today,
    ).select_related("employee")
    for req in qs:
        try:
            auto_assign_car(req=req, actor=actor)
            assigned += 1
        except RequestServiceError as exc:
            created = _log_once_per_day(
                actor=actor,
                action="request.auto_assign_blocked",
                req=req,
                today=today,
                payload={"reason": str(exc)},
            )
            if created:
                notify_request_event(
                    "auto_assign_blocked",
                    req,
                    actor=actor,
                    extra={"reason": str(exc)},
                )
                blocked += 1
    return assigned, blocked


def flag_stale_pending_requests(*, actor=None, today: date | None = None) -> int:
    today = today or timezone.localdate()
    stale_hours = getattr(settings, "REQUEST_PENDING_STALE_HOURS", 24)
    threshold = timezone.now() - timedelta(hours=stale_hours)
    count = 0
    qs = Request.objects.filter(
        status=Request.Status.PENDING,
        created_at__lte=threshold,
    ).select_related("employee")
    for req in qs:
        created = _log_once_per_day(
            actor=actor,
            action="request.pending_stale",
            req=req,
            today=today,
            payload={
                "created_at": req.created_at.isoformat(),
                "stale_hours": stale_hours,
            },
        )
        if created:
            notify_request_event("pending_stale", req, actor=actor)
            count += 1
    return count


def run_request_automations(*, actor=None, today: date | None = None) -> AutomationSummary:
    today = today or timezone.localdate()
    summary = AutomationSummary()
    summary.overdue_marked = mark_overdue_returns(actor=actor, today=today)
    summary.maintenance_due_marked = mark_due_cars_for_maintenance(
        actor=actor,
        today=today,
    )
    summary.auto_assigned, summary.auto_assign_blocked = retry_auto_assignment(
        actor=actor,
        today=today,
    )
    summary.return_reminders_created = create_return_reminders(actor=actor, today=today)
    summary.stale_pending_flagged = flag_stale_pending_requests(actor=actor, today=today)
    return summary
