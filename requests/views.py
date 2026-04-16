from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from core.auth import user_in_groups
from fleet.models import Car
from requests.forms import RequestCreateForm, ReturnForm
from requests.models import Request
from requests.services import (
    RequestServiceError,
    approve_request,
    assign_car,
    complete_request,
    reject_request,
    set_pending,
)


@login_required
def employee_dashboard(request):
    if not user_in_groups(request.user, ["employee"]):
        raise PermissionDenied
    if not hasattr(request.user, "employee"):
        messages.error(request, "Для пользователя не создан профиль сотрудника.")
        return redirect("employee_requests")

    qs = Request.objects.filter(employee__user=request.user)
    by_status = {row["status"]: row["c"] for row in qs.values("status").annotate(c=Count("id"))}
    latest = list(qs.select_related("car").order_by("-created_at")[:5])
    return render(
        request,
        "employee/dashboard.html",
        {
            "counts": by_status,
            "latest": latest,
        },
    )


@login_required
def employee_requests(request):
    if not user_in_groups(request.user, ["employee", "service_admin", "sys_admin"]):
        raise PermissionDenied
    qs = Request.objects.select_related("employee", "car")
    if not user_in_groups(request.user, ["service_admin", "sys_admin"]):
        qs = qs.filter(employee__user=request.user)

    status = request.GET.get("status") or ""
    q = (request.GET.get("q") or "").strip()
    if status:
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(
            Q(reason__icontains=q)
            | Q(car__vin__icontains=q)
            | Q(car__brand_model__icontains=q)
        )

    paginator = Paginator(qs.order_by("-created_at"), 20)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "employee/requests_list.html",
        {
            "page_obj": page,
            "status": status,
            "q": q,
            "statuses": Request.Status.choices,
        },
    )


@login_required
def employee_request_create(request):
    if not user_in_groups(request.user, ["employee"]):
        raise PermissionDenied
    if request.method == "POST":
        form = RequestCreateForm(request.POST)
        if form.is_valid():
            req: Request = form.save(commit=False)
            if not hasattr(request.user, "employee"):
                messages.error(request, "Для пользователя не создан профиль сотрудника.")
            else:
                req.employee = request.user.employee
                req.status = Request.Status.PENDING
                req.save()
                messages.success(request, "Заявка создана.")
                return redirect("employee_requests")
    else:
        form = RequestCreateForm()

    return render(request, "employee/request_create.html", {"form": form})


@login_required
def admin_dashboard(request):
    if not user_in_groups(request.user, ["service_admin"]):
        raise PermissionDenied
    by_status = (
        Request.objects.values("status").annotate(c=Count("id")).order_by("status")
    )
    counts = {row["status"]: row["c"] for row in by_status}
    available_cars = Car.objects.filter(status=Car.Status.AVAILABLE).count()
    total_cars = Car.objects.count()
    return render(
        request,
        "admin/dashboard.html",
        {
            "counts": counts,
            "available_cars": available_cars,
            "total_cars": total_cars,
            "statuses": Request.Status,
        },
    )


@login_required
def admin_requests(request):
    if not user_in_groups(request.user, ["service_admin"]):
        raise PermissionDenied
    qs = Request.objects.select_related("employee", "car").all()
    status = request.GET.get("status") or ""
    q = (request.GET.get("q") or "").strip()
    if status:
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(
            Q(reason__icontains=q)
            | Q(employee__full_name__icontains=q)
            | Q(car__vin__icontains=q)
            | Q(car__brand_model__icontains=q)
        )

    paginator = Paginator(qs.order_by("-created_at"), 20)
    page = paginator.get_page(request.GET.get("page"))
    available_cars = list(Car.objects.filter(status=Car.Status.AVAILABLE).order_by("brand_model", "vin"))

    return render(
        request,
        "admin/requests_list.html",
        {
            "page_obj": page,
            "status": status,
            "q": q,
            "statuses": Request.Status.choices,
            "available_cars": available_cars,
        },
    )


@login_required
def admin_request_approve(request, pk: int):
    if not user_in_groups(request.user, ["service_admin"]):
        raise PermissionDenied
    req = get_object_or_404(Request, pk=pk)
    try:
        approve_request(req=req, actor=request.user)
        messages.success(request, f"Заявка #{req.id} одобрена.")
    except RequestServiceError as e:
        messages.error(request, str(e))
    return redirect("admin_requests")


@login_required
def admin_request_reject(request, pk: int):
    if not user_in_groups(request.user, ["service_admin"]):
        raise PermissionDenied
    req = get_object_or_404(Request, pk=pk)
    try:
        reject_request(req=req, actor=request.user, reason=request.POST.get("reason") if request.method == "POST" else None)
        messages.success(request, f"Заявка #{req.id} отклонена.")
    except RequestServiceError as e:
        messages.error(request, str(e))
    return redirect("admin_requests")


@login_required
def admin_request_pending(request, pk: int):
    if not user_in_groups(request.user, ["service_admin"]):
        raise PermissionDenied
    req = get_object_or_404(Request, pk=pk)
    try:
        set_pending(req=req, actor=request.user)
        messages.success(request, f"Заявка #{req.id} переведена в ожидание.")
    except RequestServiceError as e:
        messages.error(request, str(e))
    return redirect("admin_requests")


@login_required
def admin_request_assign(request, pk: int):
    if not user_in_groups(request.user, ["service_admin"]):
        raise PermissionDenied
    req = get_object_or_404(Request.objects.select_related("car"), pk=pk)
    car_id = request.POST.get("car_id")
    if not car_id:
        messages.error(request, "Выберите автомобиль.")
        return redirect("admin_requests")
    car = get_object_or_404(Car, pk=car_id)
    try:
        assign_car(req=req, car=car, actor=request.user)
        messages.success(request, f"Авто назначено на заявку #{req.id}.")
    except RequestServiceError as e:
        messages.error(request, str(e))
    return redirect("admin_requests")


@login_required
def admin_request_return(request, pk: int):
    if not user_in_groups(request.user, ["service_admin"]):
        raise PermissionDenied
    req = get_object_or_404(Request.objects.select_related("employee", "car"), pk=pk)
    if request.method == "POST":
        form = ReturnForm(request.POST)
        if form.is_valid():
            try:
                complete_request(req=req, actor=request.user, defects=form.cleaned_data.get("defects"))
                messages.success(request, f"Заявка #{req.id} завершена. Авто возвращено.")
                return redirect("admin_requests")
            except RequestServiceError as e:
                messages.error(request, str(e))
    else:
        form = ReturnForm()

    return render(request, "admin/request_return.html", {"form": form, "req": req})


@login_required
def admin_reports(request):
    if not user_in_groups(request.user, ["service_admin"]):
        raise PermissionDenied
    return HttpResponse("Отчёты (UI будет добавлен на шаге templates-ui).")
