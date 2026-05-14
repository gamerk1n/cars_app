from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import get_object_or_404, render
from django.utils.dateparse import parse_date

from core.auth import user_in_groups
from fleet.models import Car
from reports.calculations import calculate_fleet_metrics, calculate_report_usage
from reports.models import Report
from requests.models import Request


@login_required
def admin_reports(request):
    if not user_in_groups(request.user, ["service_admin"]):
        raise PermissionDenied
    start_date = request.GET.get("start_date") or ""
    end_date = request.GET.get("end_date") or ""
    period_start = parse_date(start_date) if start_date else None
    period_end = parse_date(end_date) if end_date else None

    reports_qs = Report.objects.select_related("employee", "car", "request").all()
    if period_start:
        reports_qs = reports_qs.filter(start_date__gte=period_start)
    if period_end:
        reports_qs = reports_qs.filter(end_date__lte=period_end)

    paginator = Paginator(reports_qs.order_by("-created_at"), 20)
    page = paginator.get_page(request.GET.get("page"))
    calculation_reports = list(
        reports_qs.select_related("employee", "car", "request").prefetch_related(
            "request__inspections"
        )
    )
    fleet_metrics = calculate_fleet_metrics(
        calculation_reports,
        total_cars=Car.objects.count(),
        period_start=period_start,
        period_end=period_end,
    )

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
            "fleet_metrics": fleet_metrics,
        },
    )


@login_required
def admin_report_detail(request, pk: int):
    if not user_in_groups(request.user, ["service_admin"]):
        raise PermissionDenied

    report = get_object_or_404(
        Report.objects.select_related("employee", "car", "request").prefetch_related(
            "request__inspections"
        ),
        pk=pk,
    )
    return render(
        request,
        "admin/report_detail.html",
        {"report": report, "calculation": calculate_report_usage(report)},
    )
