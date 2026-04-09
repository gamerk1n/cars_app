from django.db import models

from accounts.models import Employee
from fleet.models import Car
from requests.models import Request


class Report(models.Model):
    name = models.CharField(max_length=160)
    request = models.ForeignKey(
        Request, on_delete=models.CASCADE, related_name="reports"
    )
    car = models.ForeignKey(Car, on_delete=models.PROTECT, related_name="reports")
    employee = models.ForeignKey(
        Employee, on_delete=models.PROTECT, related_name="reports"
    )
    start_date = models.DateField()
    end_date = models.DateField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["start_date"]),
            models.Index(fields=["end_date"]),
        ]

    def __str__(self) -> str:
        return self.name
