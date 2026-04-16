from django.db import models
from django.utils import timezone

from accounts.models import Employee
from fleet.models import Car


class Request(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Ожидание"
        APPROVED = "approved", "Одобрена"
        REJECTED = "rejected", "Отклонена"
        COMPLETED = "completed", "Завершена"

    reason = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="requests"
    )
    car = models.ForeignKey(
        Car, null=True, blank=True, on_delete=models.SET_NULL, related_name="requests"
    )

    assigned_at = models.DateTimeField(null=True, blank=True)
    returned_at = models.DateTimeField(null=True, blank=True)
    return_defects = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["start_date"]),
            models.Index(fields=["end_date"]),
            models.Index(fields=["employee", "status"]),
        ]

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.start_date > self.end_date:
            from django.core.exceptions import ValidationError

            raise ValidationError({"end_date": "Дата окончания должна быть не раньше даты начала."})

    def mark_assigned_now(self):
        self.assigned_at = self.assigned_at or timezone.now()

    def mark_returned_now(self):
        self.returned_at = self.returned_at or timezone.now()

    def __str__(self) -> str:
        return f"Заявка #{self.pk} ({self.employee})"
