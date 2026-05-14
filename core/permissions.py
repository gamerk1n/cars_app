from rest_framework.permissions import BasePermission

from accounts.roles import REQUESTER_ROLES, SERVICE_ADMIN, SYS_ADMIN


def _in_group(user, name: str) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name=name).exists()


class IsServiceAdmin(BasePermission):
    def has_permission(self, request, view):
        return _in_group(request.user, SERVICE_ADMIN)


class IsEmployee(BasePermission):
    def has_permission(self, request, view):
        allowed_roles = (*REQUESTER_ROLES, SERVICE_ADMIN, SYS_ADMIN)
        return any(_in_group(request.user, role) for role in allowed_roles)


class IsSysAdmin(BasePermission):
    def has_permission(self, request, view):
        return _in_group(request.user, SYS_ADMIN)
