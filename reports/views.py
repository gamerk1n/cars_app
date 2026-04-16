from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import get_object_or_404, render

from core.auth import user_in_groups
from fleet.models import Car
from reports.models import Report
from requests.models import Request


@login_required
def admin_reports(request):
    if not user_in_groups(request.user, ["service_admin"]):
        raise PermissionDenied
    start_date = request.GET.get("start_date") or ""
    end_date = request.GET.get("end_date") or ""

    reports_qs = Report.objects.select_related("employee", "car", "request").all()
    if start_date:
        reports_qs = reports_qs.filter(start_date__gte=start_date)
    if end_date:
        reports_qs = reports_qs.filter(end_date__lte=end_date)

    paginator = Paginator(reports_qs.order_by("-created_at"), 20)
    page = paginator.get_page(request.GET.get("page"))

    request_counts = {
        row["status"]: row["c"]
        for row in Request.objects.values("status").annotate(c=Count("id"))
    }
    car_counts = {
        row["status"]: row["c"] for row in Car.objects.values("status").annotate(c=Count("id"))
    }

    top_cars = list(
        reports_qs.values("car__brand_model", "car__vin")
        .annotate(c=Count("id"))
        .order_by("-c", "car__brand_model")[:5]
    )
    top_employees = list(
        reports_qs.values("employee__full_name")
        .annotate(c=Count("id"))
        .order_by("-c", "employee__full_name")[:5]
    )

    return render(
        request,
        "admin/reports.html",
        {
            "page_obj": page,
            "start_date": start_date,
            "end_date": end_date,
            "request_counts": request_counts,
            "car_counts": car_counts,
            "request_statuses": Request.Status.choices,
            "car_statuses": Car.Status.choices,
            "top_cars": top_cars,
            "top_employees": top_employees,
        },
    )


@login_required
def admin_report_detail(request, pk: int):
    if not user_in_groups(request.user, ["service_admin"]):
        raise PermissionDenied

    report = get_object_or_404(
        Report.objects.select_related("employee", "car", "request"),
        pk=pk,
    )
    return render(request, "admin/report_detail.html", {"report": report})
