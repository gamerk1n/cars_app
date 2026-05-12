from __future__ import annotations

import logging
from typing import Any

from django.db import transaction

from audit.models import ActionLog

logger = logging.getLogger(__name__)


EVENT_DEFINITIONS = {
    "request.approve": (
        ActionLog.Category.REQUEST,
        ActionLog.Severity.INFO,
        "Заявка одобрена",
    ),
    "request.reject": (
        ActionLog.Category.REQUEST,
        ActionLog.Severity.WARNING,
        "Заявка отклонена",
    ),
    "request.assign_car": (
        ActionLog.Category.RESERVATION,
        ActionLog.Severity.INFO,
        "Автомобиль забронирован",
    ),
    "request.auto_assign_car": (
        ActionLog.Category.RESERVATION,
        ActionLog.Severity.INFO,
        "Автомобиль назначен автоматически",
    ),
    "request.auto_assign_blocked": (
        ActionLog.Category.RESERVATION,
        ActionLog.Severity.WARNING,
        "Автоназначение не выполнено",
    ),
    "request.auto_approve": (
        ActionLog.Category.REQUEST,
        ActionLog.Severity.INFO,
        "Заявка автоодобрена",
    ),
    "request.auto_approval_blocked": (
        ActionLog.Category.REQUEST,
        ActionLog.Severity.WARNING,
        "Заявка требует ручной проверки",
    ),
    "request.complete": (
        ActionLog.Category.REQUEST,
        ActionLog.Severity.INFO,
        "Заявка завершена",
    ),
    "request.return_due_soon": (
        ActionLog.Category.REQUEST,
        ActionLog.Severity.WARNING,
        "Скоро возврат автомобиля",
    ),
    "request.return_overdue": (
        ActionLog.Category.REQUEST,
        ActionLog.Severity.WARNING,
        "Возврат автомобиля просрочен",
    ),
    "request.pending_stale": (
        ActionLog.Category.REQUEST,
        ActionLog.Severity.WARNING,
        "Заявка зависла в ожидании",
    ),
    "request.inspection.issue": (
        ActionLog.Category.INSPECTION,
        ActionLog.Severity.INFO,
        "Создан акт выдачи",
    ),
    "request.inspection.return": (
        ActionLog.Category.INSPECTION,
        ActionLog.Severity.INFO,
        "Создан акт возврата",
    ),
    "request.reservation_cancel": (
        ActionLog.Category.RESERVATION,
        ActionLog.Severity.WARNING,
        "Бронь отменена",
    ),
    "request.reservation_complete": (
        ActionLog.Category.RESERVATION,
        ActionLog.Severity.INFO,
        "Бронь завершена",
    ),
    "car.maintenance_due": (
        ActionLog.Category.MAINTENANCE,
        ActionLog.Severity.WARNING,
        "Автомобиль требует ТО",
    ),
    "car.telematics_mileage": (
        ActionLog.Category.FLEET,
        ActionLog.Severity.INFO,
        "Пробег обновлён из телематики",
    ),
    "car.telematics_mileage_ignored": (
        ActionLog.Category.FLEET,
        ActionLog.Severity.WARNING,
        "Пробег из телематики не принят",
    ),
    "notification.request": (
        ActionLog.Category.NOTIFICATION,
        ActionLog.Severity.INFO,
        "Отправлено уведомление",
    ),
}


def _fallback_event_definition(action: str, object_type: str):
    if action.startswith("notification."):
        return ActionLog.Category.NOTIFICATION, ActionLog.Severity.INFO, "Уведомление"
    if action.startswith("request.inspection"):
        return ActionLog.Category.INSPECTION, ActionLog.Severity.INFO, action
    if action.startswith("request.reservation"):
        return ActionLog.Category.RESERVATION, ActionLog.Severity.INFO, action
    if action.startswith("request."):
        return ActionLog.Category.REQUEST, ActionLog.Severity.INFO, action
    if action.startswith("car.") or object_type.startswith("fleet."):
        return ActionLog.Category.FLEET, ActionLog.Severity.INFO, action
    if action.startswith("report."):
        return ActionLog.Category.REPORT, ActionLog.Severity.INFO, action
    return ActionLog.Category.SYSTEM, ActionLog.Severity.INFO, action


def _as_positive_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _resolve_context(*, obj, payload: dict[str, Any]) -> tuple[int | None, int | None]:
    object_type = obj._meta.label_lower
    request_id = payload.get("request_id")
    car_id = payload.get("car_id")

    if object_type == "requests.request":
        request_id = obj.pk
        car_id = car_id or getattr(obj, "car_id", None)
    elif object_type == "requests.reservation":
        request_id = obj.request_id
        car_id = obj.car_id
    elif object_type == "requests.vehicleinspection":
        request_id = obj.request_id
        car_id = obj.car_id
    elif object_type == "fleet.car":
        car_id = obj.pk
    elif hasattr(obj, "request_id"):
        request_id = request_id or getattr(obj, "request_id", None)
    if hasattr(obj, "car_id"):
        car_id = car_id or getattr(obj, "car_id", None)
    return _as_positive_int(request_id), _as_positive_int(car_id)


def _build_message(*, title: str, payload: dict[str, Any]) -> str:
    if "message" in payload:
        return str(payload["message"])
    if "reason" in payload:
        return f"{title}: {payload['reason']}"
    if "reasons" in payload and payload["reasons"]:
        return f"{title}: " + "; ".join(str(item) for item in payload["reasons"])
    return ""


@transaction.atomic
def log_action(
    *,
    actor,
    action: str,
    obj,
    payload: dict[str, Any] | None = None,
    category: str | None = None,
    severity: str | None = None,
    title: str | None = None,
    message: str | None = None,
) -> ActionLog:
    payload = payload or {}
    default_category, default_severity, default_title = EVENT_DEFINITIONS.get(
        action,
        _fallback_event_definition(action, obj._meta.label_lower),
    )
    resolved_title = title or default_title
    request_id, car_id = _resolve_context(obj=obj, payload=payload)
    log = ActionLog.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        object_type=obj._meta.label_lower,
        object_id=str(obj.pk),
        category=category or default_category,
        severity=severity or default_severity,
        title=resolved_title,
        message=message if message is not None else _build_message(title=resolved_title, payload=payload),
        request_id=request_id,
        car_id=car_id,
        payload=payload,
    )
    try:
        from integrations.outbox import enqueue_action_log_event

        enqueue_action_log_event(log)
    except Exception:
        logger.exception("Failed to enqueue integration event for action log %s", log.pk)
    return log
