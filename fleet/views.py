from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from core.auth import user_in_groups
from fleet.forms import CarForm, MaintenanceRecordForm
from fleet.models import Car, MaintenanceRecord
from fleet.qr import qr_svg
from fleet.services import update_car_mileage
from requests.models import Reservation, VehicleInspection


@login_required
def admin_cars(request):
    if not user_in_groups(request.user, ["service_admin"]):
        raise PermissionDenied
    qs = Car.objects.all()
    status = request.GET.get("status") or ""
    q = (request.GET.get("q") or "").strip()
    if status:
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(Q(brand_model__icontains=q) | Q(vin__icontains=q))

    paginator = Paginator(qs.order_by("brand_model", "vin"), 20)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "admin/cars_list.html",
        {"page_obj": page, "status": status, "q": q, "statuses": Car.Status.choices},
    )


@login_required
def admin_car_qr_svg(request, pk: int):
    if not user_in_groups(request.user, ["service_admin"]):
        raise PermissionDenied
    car = get_object_or_404(Car, pk=pk)
    qr_url = request.build_absolute_uri(reverse("admin_car_qr_card", args=[car.pk]))
    try:
        svg = qr_svg(qr_url)
    except ValueError as exc:
        return HttpResponse(str(exc), status=400)
    return HttpResponse(svg, content_type="image/svg+xml")


@login_required
def admin_car_qr_card(request, pk: int):
    if not user_in_groups(request.user, ["service_admin"]):
        raise PermissionDenied
    car = get_object_or_404(Car, pk=pk)
    today = timezone.localdate()
    reservation = (
        Reservation.objects.filter(
            car=car,
            status=Reservation.Status.ACTIVE,
            start_date__lte=today,
            end_date__gte=today,
        )
        .select_related("request__employee")
        .order_by("start_date", "id")
        .first()
    )
    if reservation is None:
        reservation = (
            Reservation.objects.filter(
                car=car,
                status=Reservation.Status.ACTIVE,
                start_date__gt=today,
            )
            .select_related("request__employee")
            .order_by("start_date", "id")
            .first()
        )
    active_request = reservation.request if reservation else None
    inspections = {}
    if active_request:
        inspections = {
            inspection.kind: inspection
            for inspection in active_request.inspections.all()
        }
    return render(
        request,
        "admin/car_qr_card.html",
        {
            "car": car,
            "active_request": active_request,
            "issue_inspection": inspections.get(VehicleInspection.Kind.ISSUE),
            "return_inspection": inspections.get(VehicleInspection.Kind.RETURN),
        },
    )


@login_required
def admin_car_create(request):
    if not user_in_groups(request.user, ["service_admin"]):
        raise PermissionDenied
    if request.method == "POST":
        form = CarForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Автомобиль добавлен.")
            return redirect("admin_cars")
    else:
        form = CarForm()
    return render(request, "admin/car_form.html", {"form": form, "mode": "create"})


@login_required
def admin_car_edit(request, pk: int):
    if not user_in_groups(request.user, ["service_admin"]):
        raise PermissionDenied
    car = get_object_or_404(Car, pk=pk)
    if request.method == "POST":
        form = CarForm(request.POST, instance=car)
        if form.is_valid():
            form.save()
            messages.success(request, "Автомобиль обновлён.")
            return redirect("admin_cars")
    else:
        form = CarForm(instance=car)
    return render(request, "admin/car_form.html", {"form": form, "mode": "edit", "car": car})


@login_required
def admin_car_maintenance(request, pk: int):
    if not user_in_groups(request.user, ["service_admin"]):
        raise PermissionDenied
    car = get_object_or_404(Car, pk=pk)

    if request.method == "POST":
        form = MaintenanceRecordForm(request.POST)
        if form.is_valid():
            record: MaintenanceRecord = form.save(commit=False)
            record.car = car
            record.created_by = request.user
            record.save()
            update_car_mileage(car=car, mileage=record.mileage)
            messages.success(request, "Запись ремонта/ТО добавлена.")
            return redirect("admin_car_maintenance", pk=car.pk)
    else:
        form = MaintenanceRecordForm()

    records = car.maintenance_records.select_related("request", "created_by")
    return render(
        request,
        "admin/car_maintenance.html",
        {
            "car": car,
            "form": form,
            "records": records,
        },
    )
