from django.contrib import admin

from fleet.models import Car


@admin.register(Car)
class CarAdmin(admin.ModelAdmin):
    list_display = ("brand_model", "vin", "status", "color", "type", "updated_at")
    list_filter = ("status", "type")
    search_fields = ("brand_model", "vin")
    ordering = ("brand_model", "vin")
