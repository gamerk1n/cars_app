from __future__ import annotations

from typing import Any

from django.db import transaction

from audit.models import ActionLog


@transaction.atomic
def log_action(*, actor, action: str, obj, payload: dict[str, Any] | None = None) -> ActionLog:
    payload = payload or {}
    return ActionLog.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        object_type=obj._meta.label_lower,
        object_id=str(obj.pk),
        payload=payload,
    )
