from django.db import models
from django.conf import settings


class Employee(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="employee"
    )
    full_name = models.CharField(max_length=160)
    position = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["full_name"]
        indexes = [
            models.Index(fields=["full_name"]),
        ]

    def __str__(self) -> str:
        return self.full_name
