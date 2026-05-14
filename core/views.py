from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from accounts.roles import REQUESTER_ROLES, SERVICE_ADMIN, SYS_ADMIN


@login_required
def home(request):
    user = request.user
    if user.is_superuser or user.groups.filter(name=SYS_ADMIN).exists():
        return redirect("sysadmin_dashboard")
    if user.groups.filter(name=SERVICE_ADMIN).exists():
        return redirect("admin_dashboard")
    if user.groups.filter(name__in=REQUESTER_ROLES).exists():
        return redirect("employee_dashboard")
    return redirect("employee_dashboard")
