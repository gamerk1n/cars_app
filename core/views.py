from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


@login_required
def home(request):
    user = request.user
    if user.is_superuser or user.groups.filter(name="sys_admin").exists():
        return redirect("sysadmin_dashboard")
    if user.groups.filter(name="service_admin").exists():
        return redirect("admin_dashboard")
    return redirect("employee_dashboard")
