from django.contrib import admin

from reports.models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("name", "employee", "car", "start_date", "end_date", "created_at")
    list_filter = ("start_date", "end_date")
    search_fields = ("name", "employee__full_name", "car__vin", "car__brand_model")
    autocomplete_fields = ("employee", "car", "request")
