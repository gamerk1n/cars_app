from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from accounts.models import Employee
from fleet.models import Car


def request_attachment_upload_to(instance, filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    return f"request_attachments/{uuid4().hex}{suffix}"


def inspection_photo_upload_to(instance, filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    return f"inspection_photos/{uuid4().hex}{suffix}"


class Request(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Ожидание"
        APPROVED = "approved", "Одобрена"
        REJECTED = "rejected", "Отклонена"
        OVERDUE = "overdue", "Просрочена"
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
    attachment = models.FileField(upload_to=request_attachment_upload_to, blank=True)
    attachment_original_name = models.CharField(max_length=255, blank=True)
    rules_accepted = models.BooleanField(default=False)
    rules_accepted_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"], name="requests_re_status_039311_idx"),
            models.Index(fields=["start_date"], name="requests_re_start_d_97e5a7_idx"),
            models.Index(fields=["end_date"], name="requests_re_end_dat_b87154_idx"),
            models.Index(fields=["employee", "status"], name="requests_re_employe_1afa24_idx"),
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


class Reservation(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Активна"
        CANCELLED = "cancelled", "Отменена"
        COMPLETED = "completed", "Завершена"

    request = models.OneToOneField(
        Request, on_delete=models.CASCADE, related_name="reservation"
    )
    car = models.ForeignKey(
        Car, on_delete=models.PROTECT, related_name="reservations"
    )
    employee = models.ForeignKey(
        Employee, on_delete=models.PROTECT, related_name="reservations"
    )
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reservations_created",
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start_date", "end_date", "id"]
        indexes = [
            models.Index(
                fields=["car", "status", "start_date", "end_date"],
                name="requests_re_car_id_9bbb5a_idx",
            ),
            models.Index(fields=["employee", "status"], name="req_res_emp_2ea67b_idx"),
            models.Index(fields=["status"], name="requests_re_status_b4c635_idx"),
        ]

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.start_date > self.end_date:
            from django.core.exceptions import ValidationError

            raise ValidationError({"end_date": "Дата окончания должна быть не раньше даты начала."})

    def is_current(self, *, today=None) -> bool:
        today = today or timezone.localdate()
        return self.start_date <= today <= self.end_date

    def __str__(self) -> str:
        return f"{self.car} / заявка #{self.request_id} ({self.start_date} - {self.end_date})"


class VehicleInspection(models.Model):
    class Kind(models.TextChoices):
        ISSUE = "issue", "Выдача"
        RETURN = "return", "Возврат"

    DAMAGE_ZONE_CHOICES = [
        ("front", "Передняя часть"),
        ("rear", "Задняя часть"),
        ("left", "Левая сторона"),
        ("right", "Правая сторона"),
        ("roof", "Крыша"),
        ("glass", "Стёкла"),
        ("wheels", "Колёса"),
        ("interior", "Салон"),
        ("documents", "Документы/ключи"),
    ]

    request = models.ForeignKey(
        Request, on_delete=models.CASCADE, related_name="inspections"
    )
    car = models.ForeignKey(
        Car, on_delete=models.PROTECT, related_name="inspections"
    )
    employee = models.ForeignKey(
        Employee, on_delete=models.PROTECT, related_name="vehicle_inspections"
    )
    kind = models.CharField(max_length=20, choices=Kind.choices)
    mileage = models.PositiveIntegerField()
    fuel_level = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    exterior_condition = models.TextField(blank=True)
    interior_condition = models.TextField(blank=True)
    damage_zones = models.JSONField(default=list, blank=True)
    defects = models.TextField(blank=True)
    employee_signature = models.CharField(max_length=160)
    inspector_signature = models.CharField(max_length=160)
    completed_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="vehicle_inspections_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-completed_at", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["request", "kind"],
                name="unique_request_inspection_kind",
            )
        ]
        indexes = [
            models.Index(fields=["request", "kind"], name="requests_ve_request_7e2616_idx"),
            models.Index(fields=["car", "kind"], name="requests_ve_car_id_34a4cd_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} по заявке #{self.request_id}"


class VehicleInspectionPhoto(models.Model):
    class Label(models.TextChoices):
        EXTERIOR = "exterior", "Кузов"
        INTERIOR = "interior", "Салон"
        DAMAGE = "damage", "Повреждения"
        OTHER = "other", "Другое"

    inspection = models.ForeignKey(
        VehicleInspection, on_delete=models.CASCADE, related_name="photos"
    )
    image = models.FileField(upload_to=inspection_photo_upload_to)
    label = models.CharField(
        max_length=20, choices=Label.choices, default=Label.OTHER
    )
    original_name = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self) -> str:
        return f"{self.get_label_display()} #{self.inspection_id}"
