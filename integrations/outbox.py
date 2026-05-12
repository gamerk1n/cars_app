from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from audit.models import ActionLog
from integrations.models import IntegrationEvent


@dataclass(frozen=True)
class DispatchSummary:
    configured: bool
    selected: int
    sent: int
    failed: int

    def as_dict(self) -> dict[str, int | bool]:
        return {
            "configured": self.configured,
            "selected": self.selected,
            "sent": self.sent,
            "failed": self.failed,
        }


def action_log_payload(log: ActionLog) -> dict[str, Any]:
    return {
        "event_type": log.action,
        "action_log_id": log.id,
        "category": log.category,
        "severity": log.severity,
        "title": log.title,
        "message": log.message,
        "request_id": log.request_id,
        "car_id": log.car_id,
        "object": {
            "type": log.object_type,
            "id": log.object_id,
        },
        "actor": {
            "id": log.actor_id,
            "username": log.actor.username if log.actor_id and log.actor else "",
        },
        "payload": log.payload,
        "occurred_at": log.created_at.isoformat(),
    }


def enqueue_action_log_event(log: ActionLog) -> IntegrationEvent | None:
    if not getattr(settings, "INTEGRATIONS_OUTBOX_ENABLED", True):
        return None
    event, _created = IntegrationEvent.objects.get_or_create(
        action_log=log,
        defaults={
            "event_type": log.action,
            "payload": action_log_payload(log),
        },
    )
    return event


def _post_json(url: str, payload: dict[str, Any], *, timeout: int) -> tuple[bool, str]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", response.getcode())
            if 200 <= status < 300:
                return True, ""
            return False, f"HTTP {status}"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return False, str(exc)


def dispatch_pending_events(*, limit: int = 100) -> DispatchSummary:
    webhook_url = getattr(settings, "INTEGRATIONS_WEBHOOK_URL", "")
    if not webhook_url:
        return DispatchSummary(configured=False, selected=0, sent=0, failed=0)

    now = timezone.now()
    events = list(
        IntegrationEvent.objects.filter(status=IntegrationEvent.Status.PENDING)
        .filter(Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now))
        .order_by("created_at", "id")[:limit]
    )
    timeout = getattr(settings, "INTEGRATIONS_WEBHOOK_TIMEOUT_SECONDS", 3)
    max_attempts = getattr(settings, "INTEGRATIONS_OUTBOX_MAX_ATTEMPTS", 5)
    sent = 0
    failed = 0

    for event in events:
        ok, error = _post_json(webhook_url, event.payload, timeout=timeout)
        event.attempts += 1
        if ok:
            event.status = IntegrationEvent.Status.SENT
            event.sent_at = timezone.now()
            event.last_error = ""
            event.next_attempt_at = None
            sent += 1
        else:
            event.last_error = error[:2000]
            if event.attempts >= max_attempts:
                event.status = IntegrationEvent.Status.FAILED
            else:
                event.next_attempt_at = timezone.now() + timedelta(minutes=event.attempts * 5)
            failed += 1
        event.save(
            update_fields=[
                "attempts",
                "status",
                "sent_at",
                "last_error",
                "next_attempt_at",
                "updated_at",
            ]
        )

    return DispatchSummary(configured=True, selected=len(events), sent=sent, failed=failed)
