from __future__ import annotations

from typing import Iterable

from django.contrib.auth.mixins import AccessMixin
from django.core.exceptions import PermissionDenied


def user_in_groups(user, groups: Iterable[str]) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=list(groups)).exists()


class GroupRequiredMixin(AccessMixin):
    group_required: tuple[str, ...] = ()

    def dispatch(self, request, *args, **kwargs):
        if not user_in_groups(request.user, self.group_required):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)
