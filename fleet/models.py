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

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["brand_model", "vin"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["vin"]),
        ]

    def __str__(self) -> str:
        return f"{self.brand_model} ({self.vin})"
