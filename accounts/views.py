from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from accounts.forms import UserCreateForm, UserUpdateForm
from audit.models import ActionLog
from core.auth import user_in_groups

User = get_user_model()


@login_required
def sysadmin_dashboard(request):
    if not user_in_groups(request.user, ["sys_admin"]):
        raise PermissionDenied
    groups = Group.objects.filter(name__in=["employee", "service_admin", "sys_admin"]).order_by("name")
    counts = {g.name: g.user_set.count() for g in groups}
    total_users = User.objects.count()
    return render(
        request,
        "sysadmin/dashboard.html",
        {"counts": counts, "total_users": total_users},
    )


@login_required
def sysadmin_users(request):
    if not user_in_groups(request.user, ["sys_admin"]):
        raise PermissionDenied
    qs = User.objects.all()
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(username__icontains=q) | Q(email__icontains=q))

    paginator = Paginator(qs.order_by("username"), 20)
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "sysadmin/users_list.html", {"page_obj": page, "q": q})


@login_required
def sysadmin_user_create(request):
    if not user_in_groups(request.user, ["sys_admin"]):
        raise PermissionDenied
    if request.method == "POST":
        form = UserCreateForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data["password"])
            user.save()
            form.save_m2m()
            messages.success(request, "Пользователь создан.")
            return redirect("sysadmin_users")
    else:
        form = UserCreateForm()
    return render(request, "sysadmin/user_form.html", {"form": form, "mode": "create"})


@login_required
def sysadmin_user_edit(request, pk: int):
    if not user_in_groups(request.user, ["sys_admin"]):
        raise PermissionDenied
    user = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        form = UserUpdateForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, "Пользователь обновлён.")
            return redirect("sysadmin_users")
    else:
        form = UserUpdateForm(instance=user)
    return render(request, "sysadmin/user_form.html", {"form": form, "mode": "edit", "target_user": user})


@login_required
def sysadmin_user_delete(request, pk: int):
    if not user_in_groups(request.user, ["sys_admin"]):
        raise PermissionDenied
    user = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        if user.id == request.user.id:
            messages.error(request, "Нельзя удалить самого себя.")
        else:
            user.delete()
            messages.success(request, "Пользователь удалён.")
        return redirect("sysadmin_users")
    return render(request, "sysadmin/user_delete.html", {"target_user": user})


@login_required
def sysadmin_logs(request):
    if not user_in_groups(request.user, ["sys_admin"]):
        raise PermissionDenied
    qs = ActionLog.objects.select_related("actor").all()
    q = (request.GET.get("q") or "").strip()
    action = (request.GET.get("action") or "").strip()
    if action:
        qs = qs.filter(action=action)
    if q:
        qs = qs.filter(
            Q(actor__username__icontains=q)
            | Q(object_type__icontains=q)
            | Q(object_id__icontains=q)
        )

    paginator = Paginator(qs.order_by("-created_at"), 50)
    page = paginator.get_page(request.GET.get("page"))
    actions = list(ActionLog.objects.values_list("action", flat=True).distinct().order_by("action")[:200])
    return render(request, "sysadmin/logs_list.html", {"page_obj": page, "q": q, "action": action, "actions": actions})
