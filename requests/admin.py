from django.contrib import admin

from requests.models import Reservation, Request, VehicleInspection, VehicleInspectionPhoto


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
        "rules_accepted",
        "created_at",
    )
    list_filter = ("status", "rules_accepted", "start_date", "end_date")
    search_fields = ("reason", "employee__full_name", "car__vin", "car__brand_model")
    autocomplete_fields = ("employee", "car")


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "request",
        "car",
        "employee",
        "start_date",
        "end_date",
        "status",
    )
    list_filter = ("status", "start_date", "end_date")
    search_fields = ("=request__id", "employee__full_name", "car__vin", "car__brand_model")
    autocomplete_fields = ("request", "car", "employee", "created_by")


class VehicleInspectionPhotoInline(admin.TabularInline):
    model = VehicleInspectionPhoto
    extra = 0


@admin.register(VehicleInspection)
class VehicleInspectionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "request",
        "kind",
        "car",
        "employee",
        "mileage",
        "fuel_level",
        "completed_at",
    )
    list_filter = ("kind", "completed_at")
    search_fields = ("=request__id", "employee__full_name", "car__vin", "car__brand_model")
    autocomplete_fields = ("request", "car", "employee", "created_by")
    inlines = [VehicleInspectionPhotoInline]
