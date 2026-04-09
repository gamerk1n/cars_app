from rest_framework.permissions import BasePermission


def _in_group(user, name: str) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name=name).exists()


class IsServiceAdmin(BasePermission):
    def has_permission(self, request, view):
        return _in_group(request.user, "service_admin")


class IsEmployee(BasePermission):
    def has_permission(self, request, view):
        return _in_group(request.user, "employee") or _in_group(request.user, "service_admin") or _in_group(request.user, "sys_admin")


class IsSysAdmin(BasePermission):
    def has_permission(self, request, view):
        return _in_group(request.user, "sys_admin")
