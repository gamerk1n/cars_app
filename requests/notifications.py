from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail

from audit.services import log_action
from requests.models import Request


@dataclass(frozen=True)
class NotificationResult:
    event: str
    email_recipients: list[str]
    email_sent: int
    webhook_sent: bool


EMPLOYEE_EVENTS = {
    "approved",
    "assigned",
    "rejected",
    "completed",
    "return_due_soon",
    "return_overdue",
}
ADMIN_EVENTS = {
    "created",
    "auto_approval_blocked",
    "auto_assign_blocked",
    "pending_stale",
    "return_overdue",
    "defects_reported",
}


def _unique_emails(emails: list[str]) -> list[str]:
    seen = set()
    result = []
    for email in emails:
        normalized = (email or "").strip()
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result


def _employee_email(req: Request) -> str:
    return req.employee.email or req.employee.user.email


def _service_admin_emails() -> list[str]:
    user_model = get_user_model()
    return list(
        user_model.objects.filter(groups__name="service_admin")
        .exclude(email="")
        .values_list("email", flat=True)
        .distinct()
    )


def request_notification_recipients(event: str, req: Request) -> list[str]:
    emails = []
    if event in EMPLOYEE_EVENTS:
        emails.append(_employee_email(req))
    if event in ADMIN_EVENTS:
        emails.extend(_service_admin_emails())
    return _unique_emails(emails)


def _car_line(req: Request) -> str:
    if not req.car_id:
        return "Автомобиль: не назначен"
    return f"Автомобиль: {req.car.brand_model} ({req.car.vin})"


def _request_lines(req: Request) -> list[str]:
    return [
        f"Заявка: #{req.id}",
        f"Сотрудник: {req.employee.full_name}",
        f"Период: {req.start_date:%d.%m.%Y} - {req.end_date:%d.%m.%Y}",
        f"Причина: {req.reason}",
        f"Статус: {req.get_status_display()}",
        _car_line(req),
    ]


def _event_title(event: str, req: Request) -> str:
    titles = {
        "created": f"Создана заявка #{req.id}",
        "approved": f"Заявка #{req.id} одобрена",
        "assigned": f"Назначен автомобиль по заявке #{req.id}",
        "rejected": f"Заявка #{req.id} отклонена",
        "completed": f"Заявка #{req.id} завершена",
        "return_due_soon": f"Скоро возврат автомобиля по заявке #{req.id}",
        "return_overdue": f"Просрочен возврат автомобиля по заявке #{req.id}",
        "auto_approval_blocked": f"Заявка #{req.id} требует ручной проверки",
        "auto_assign_blocked": f"Не удалось автоматически назначить авто по заявке #{req.id}",
        "pending_stale": f"Заявка #{req.id} зависла в ожидании",
        "defects_reported": f"По заявке #{req.id} зафиксированы дефекты",
    }
    return titles.get(event, f"Событие по заявке #{req.id}")


def build_request_notification(event: str, req: Request, extra: dict[str, Any] | None = None) -> tuple[str, str]:
    extra = extra or {}
    subject = _event_title(event, req)
    lines = [subject, "", *_request_lines(req)]

    if event == "rejected" and extra.get("reason"):
        lines.append(f"Причина отклонения: {extra['reason']}")
    if event in {"auto_approval_blocked", "auto_assign_blocked"} and extra.get("reason"):
        lines.append(f"Причина: {extra['reason']}")
    if event == "auto_approval_blocked" and extra.get("reasons"):
        lines.append("Причины:")
        lines.extend(f"- {reason}" for reason in extra["reasons"])
    if event == "return_due_soon":
        lines.append(f"Дата возврата: {req.end_date:%d.%m.%Y}")
    if event == "return_overdue":
        lines.append(f"Плановая дата возврата: {req.end_date:%d.%m.%Y}")
    if event == "defects_reported" and extra.get("defects"):
        lines.append(f"Дефекты: {extra['defects']}")

    return subject, "\n".join(lines)


def _send_webhook(payload: dict[str, Any]) -> bool:
    webhook_url = getattr(settings, "NOTIFICATIONS_WEBHOOK_URL", "")
    if not webhook_url:
        return False

    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    timeout = getattr(settings, "NOTIFICATIONS_WEBHOOK_TIMEOUT_SECONDS", 3)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return 200 <= response.status < 300
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def notify_request_event(
    event: str,
    req: Request,
    *,
    actor=None,
    extra: dict[str, Any] | None = None,
) -> NotificationResult:
    req = Request.objects.select_related("employee__user", "car").get(pk=req.pk)
    extra = extra or {}
    recipients = request_notification_recipients(event, req)
    email_sent = 0
    webhook_sent = False

    if getattr(settings, "NOTIFICATIONS_ENABLED", True):
        subject, message = build_request_notification(event, req, extra=extra)
        if recipients and getattr(settings, "NOTIFICATIONS_EMAIL_ENABLED", True):
            email_sent = send_mail(
                subject,
                message,
                getattr(settings, "DEFAULT_FROM_EMAIL", None),
                recipients,
                fail_silently=True,
            )
        webhook_sent = _send_webhook(
            {
                "event": event,
                "request_id": req.id,
                "subject": subject,
                "message": message,
                "extra": extra,
            }
        )

    log_action(
        actor=actor,
        action="notification.request",
        obj=req,
        payload={
            "event": event,
            "email_recipients": recipients,
            "email_sent": email_sent,
            "webhook_sent": webhook_sent,
        },
    )
    return NotificationResult(
        event=event,
        email_recipients=recipients,
        email_sent=email_sent,
        webhook_sent=webhook_sent,
    )
