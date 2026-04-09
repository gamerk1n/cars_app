from django.contrib import admin

from requests.models import Request


@admin.register(Request)
class RequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "employee",
        "status",
        "start_date",
        "end_date",
        "car",
        "assigned_at",
        "returned_at",
        "created_at",
    )
    list_filter = ("status", "start_date", "end_date")
    search_fields = ("reason", "employee__full_name", "car__vin", "car__brand_model")
    autocomplete_fields = ("employee", "car")
