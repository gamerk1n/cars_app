from django.contrib import admin

from integrations.models import IntegrationEvent, TelematicsReading


@admin.register(IntegrationEvent)
class IntegrationEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "status", "attempts", "created_at", "sent_at")
    list_filter = ("status", "event_type")
    search_fields = ("event_type", "payload", "last_error")
    readonly_fields = ("created_at", "updated_at")


@admin.register(TelematicsReading)
class TelematicsReadingAdmin(admin.ModelAdmin):
    list_display = ("vin", "car", "mileage", "accepted", "source", "recorded_at")
    list_filter = ("accepted", "source")
    search_fields = ("vin", "external_event_id", "car__brand_model")
    readonly_fields = ("created_at",)
