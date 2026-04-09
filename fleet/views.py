from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from core.auth import user_in_groups
from fleet.forms import CarForm
from fleet.models import Car


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
