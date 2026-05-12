from datetime import date

from django.conf import settings
from django.db import models


class Car(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "available", "Доступен"
        ASSIGNED = "assigned", "Выдан"
        MAINTENANCE = "maintenance", "На обслуживании"

    brand_model = models.CharField(max_length=120)
    vin = models.CharField(max_length=17, unique=True)
    color = models.CharField(max_length=40, blank=True)
    type = models.CharField(max_length=40, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.AVAILABLE
    )
    current_mileage = models.PositiveIntegerField(default=0)
    next_service_date = models.DateField(null=True, blank=True)
    next_service_mileage = models.PositiveIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["brand_model", "vin"]
        indexes = [
            models.Index(fields=["status"], name="fleet_car_status_d0b34f_idx"),
            models.Index(fields=["vin"], name="fleet_car_vin_bd279d_idx"),
            models.Index(fields=["next_service_date"], name="fleet_car_next_se_97e50b_idx"),
            models.Index(fields=["next_service_mileage"], name="fleet_car_next_se_5f426f_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.brand_model} ({self.vin})"

    def is_service_due(self, *, today: date | None = None) -> bool:
        today = today or date.today()
        return bool(
            (self.next_service_date and self.next_service_date <= today)
            or (
                self.next_service_mileage is not None
                and self.current_mileage >= self.next_service_mileage
            )
        )


class MaintenanceRecord(models.Model):
    class Kind(models.TextChoices):
        REPAIR = "repair", "Ремонт"
        SERVICE = "service", "ТО"

    car = models.ForeignKey(
        Car, on_delete=models.CASCADE, related_name="maintenance_records"
    )
    request = models.ForeignKey(
        "requests.Request",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="maintenance_records",
    )
    kind = models.CharField(max_length=20, choices=Kind.choices)
    service_date = models.DateField(default=date.today)
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    contractor = models.CharField(max_length=120, blank=True)
    mileage = models.PositiveIntegerField(null=True, blank=True)
    cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="maintenance_records_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-service_date", "-created_at"]
        indexes = [
            models.Index(fields=["car", "service_date"], name="fleet_maint_car_id_fe8624_idx"),
            models.Index(fields=["kind"], name="fleet_maint_kind_10b04b_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} {self.car} от {self.service_date}"
