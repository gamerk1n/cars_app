from django.contrib import admin

from fleet.models import Car, MaintenanceRecord


@admin.register(Car)
class CarAdmin(admin.ModelAdmin):
    list_display = ("brand_model", "vin", "status", "color", "type", "updated_at")
    list_filter = ("status", "type")
    search_fields = ("brand_model", "vin")
    ordering = ("brand_model", "vin")


@admin.register(MaintenanceRecord)
class MaintenanceRecordAdmin(admin.ModelAdmin):
    list_display = ("car", "kind", "service_date", "title", "cost", "created_at")
    list_filter = ("kind", "service_date")
    search_fields = ("car__brand_model", "car__vin", "title", "description")
    autocomplete_fields = ("car", "request", "created_by")
    ordering = ("-service_date", "-created_at")
