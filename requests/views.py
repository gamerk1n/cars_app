from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Exists, OuterRef, Q
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.roles import REQUESTER_ROLES, SERVICE_ADMIN, SYS_ADMIN
from core.auth import user_in_groups
from fleet.models import Car
from requests.forms import RequestCreateForm, VehicleInspectionForm
from requests.models import Request, VehicleInspection
from requests.notifications import notify_request_event
from requests.services import (
    RequestServiceError,
    approve_request,
    assign_car,
    auto_assign_car,
    complete_request_with_inspection,
    create_vehicle_inspection,
    process_auto_approval,
    reject_request,
    set_pending,
)


@login_required
def employee_dashboard(request):
    if not user_in_groups(request.user, REQUESTER_ROLES):
        raise PermissionDenied
    if not hasattr(request.user, "employee"):
        messages.error(request, "Для пользователя не создан профиль заявителя.")
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
    if not user_in_groups(request.user, (*REQUESTER_ROLES, SERVICE_ADMIN, SYS_ADMIN)):
        raise PermissionDenied
    qs = Request.objects.select_related("employee", "car")
    if not user_in_groups(request.user, [SERVICE_ADMIN, SYS_ADMIN]):
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
            "can_create_request": user_in_groups(request.user, REQUESTER_ROLES),
        },
    )


@login_required
def employee_request_create(request):
    if not user_in_groups(request.user, REQUESTER_ROLES):
        raise PermissionDenied
    if request.method == "POST":
        form = RequestCreateForm(request.POST, request.FILES)
        if form.is_valid():
            req: Request = form.save(commit=False)
            if not hasattr(request.user, "employee"):
                messages.error(request, "Для пользователя не создан профиль заявителя.")
            else:
                req.employee = request.user.employee
                req.status = Request.Status.PENDING
                req.rules_accepted_at = timezone.now()
                if req.attachment:
                    req.attachment_original_name = Path(req.attachment.name).name
                req.save()
                notify_request_event("created", req, actor=request.user)
                req, decision = process_auto_approval(req=req, actor=request.user)
                if decision.approved:
                    messages.success(request, "Заявка создана, одобрена и получила автомобиль автоматически.")
                else:
                    messages.success(request, "Заявка создана и ожидает администратора.")
                return redirect("employee_requests")
    else:
        form = RequestCreateForm()

    return render(request, "employee/request_create.html", {"form": form})


@login_required
def request_rules(request):
    return render(request, "employee/request_rules.html")


@login_required
def request_attachment(request, pk: int):
    req = get_object_or_404(Request.objects.select_related("employee__user"), pk=pk)
    can_view_all = user_in_groups(request.user, [SERVICE_ADMIN, SYS_ADMIN])
    is_owner = req.employee.user_id == request.user.id
    if not can_view_all and not is_owner:
        raise PermissionDenied
    if not req.attachment:
        raise Http404("Файл не найден.")

    filename = req.attachment_original_name or Path(req.attachment.name).name
    return FileResponse(req.attachment.open("rb"), as_attachment=False, filename=filename)


@login_required
def admin_dashboard(request):
    if not user_in_groups(request.user, [SERVICE_ADMIN]):
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
    if not user_in_groups(request.user, [SERVICE_ADMIN]):
        raise PermissionDenied
    issue_inspections = VehicleInspection.objects.filter(
        request_id=OuterRef("pk"),
        kind=VehicleInspection.Kind.ISSUE,
    )
    return_inspections = VehicleInspection.objects.filter(
        request_id=OuterRef("pk"),
        kind=VehicleInspection.Kind.RETURN,
    )
    qs = (
        Request.objects.select_related("employee", "car")
        .annotate(
            has_issue_inspection=Exists(issue_inspections),
            has_return_inspection=Exists(return_inspections),
        )
        .all()
    )
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
    available_cars = list(
        Car.objects.exclude(status=Car.Status.MAINTENANCE).order_by("brand_model", "vin")
    )

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
    if not user_in_groups(request.user, [SERVICE_ADMIN]):
        raise PermissionDenied
    req = get_object_or_404(Request, pk=pk)
    try:
        approve_request(req=req, actor=request.user)
        messages.success(request, f"Заявка #{req.id} одобрена.")
    except RequestServiceError as e:
        messages.error(request, str(e))
    return redirect("admin_requests")


@login_required
def admin_request_auto_approve(request, pk: int):
    if not user_in_groups(request.user, [SERVICE_ADMIN]):
        raise PermissionDenied
    req = get_object_or_404(Request.objects.select_related("employee__user", "car"), pk=pk)
    try:
        req, decision = process_auto_approval(req=req, actor=request.user)
        if decision.approved:
            messages.success(request, f"Заявка #{req.id} автоодобрена, автомобиль назначен.")
        else:
            messages.error(request, "Автоодобрение недоступно: " + "; ".join(decision.reasons))
    except RequestServiceError as e:
        messages.error(request, str(e))
    return redirect("admin_requests")


@login_required
def admin_request_reject(request, pk: int):
    if not user_in_groups(request.user, [SERVICE_ADMIN]):
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
    if not user_in_groups(request.user, [SERVICE_ADMIN]):
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
    if not user_in_groups(request.user, [SERVICE_ADMIN]):
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
def admin_request_auto_assign(request, pk: int):
    if not user_in_groups(request.user, [SERVICE_ADMIN]):
        raise PermissionDenied
    req = get_object_or_404(Request.objects.select_related("car"), pk=pk)
    try:
        auto_assign_car(req=req, actor=request.user)
        messages.success(request, f"Автомобиль автоматически назначен на заявку #{req.id}.")
    except RequestServiceError as e:
        messages.error(request, str(e))
    return redirect("admin_requests")


@login_required
def admin_request_issue_inspection(request, pk: int):
    if not user_in_groups(request.user, [SERVICE_ADMIN]):
        raise PermissionDenied
    req = get_object_or_404(Request.objects.select_related("employee", "car"), pk=pk)
    if request.method == "POST":
        form = VehicleInspectionForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                create_vehicle_inspection(
                    req=req,
                    kind=VehicleInspection.Kind.ISSUE,
                    actor=request.user,
                    data=form.cleaned_data,
                    photo_files=form.photo_files(),
                )
                messages.success(request, f"Акт выдачи по заявке #{req.id} создан.")
                return redirect("admin_requests")
            except RequestServiceError as e:
                messages.error(request, str(e))
    else:
        form = VehicleInspectionForm()

    return render(
        request,
        "admin/request_inspection.html",
        {"form": form, "req": req, "kind": "issue"},
    )


@login_required
def admin_request_return(request, pk: int):
    if not user_in_groups(request.user, [SERVICE_ADMIN]):
        raise PermissionDenied
    req = get_object_or_404(Request.objects.select_related("employee", "car"), pk=pk)
    if request.method == "POST":
        form = VehicleInspectionForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                complete_request_with_inspection(
                    req=req,
                    actor=request.user,
                    inspection_data=form.cleaned_data,
                    photo_files=form.photo_files(),
                )
                messages.success(request, f"Заявка #{req.id} завершена. Акт возврата создан.")
                return redirect("admin_requests")
            except RequestServiceError as e:
                messages.error(request, str(e))
    else:
        form = VehicleInspectionForm()

    return render(
        request,
        "admin/request_inspection.html",
        {"form": form, "req": req, "kind": "return"},
    )


@login_required
def admin_reports(request):
    if not user_in_groups(request.user, [SERVICE_ADMIN]):
        raise PermissionDenied
    return HttpResponse("Отчёты (UI будет добавлен на шаге templates-ui).")
