from django.db import models


class IntegrationEvent(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает"
        SENT = "sent", "Отправлено"
        FAILED = "failed", "Ошибка"

    action_log = models.OneToOneField(
        "audit.ActionLog",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="integration_event",
    )
    event_type = models.CharField(max_length=100)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    payload = models.JSONField(default=dict)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(blank=True)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["status", "next_attempt_at"], name="integr_event_status_f202c3_idx"),
            models.Index(fields=["event_type", "status"], name="int_evt_type_e23c7c_idx"),
            models.Index(fields=["created_at"], name="int_evt_created_8c25d7_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.event_type} [{self.status}]"


class TelematicsReading(models.Model):
    car = models.ForeignKey(
        "fleet.Car", on_delete=models.CASCADE, related_name="telematics_readings"
    )
    vin = models.CharField(max_length=17)
    mileage = models.PositiveIntegerField()
    recorded_at = models.DateTimeField()
    source = models.CharField(max_length=80, blank=True)
    external_event_id = models.CharField(max_length=120, blank=True)
    accepted = models.BooleanField(default=True)
    ignored_reason = models.CharField(max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recorded_at", "-created_at"]
        indexes = [
            models.Index(fields=["car", "recorded_at"], name="integr_telem_car_id_bfda44_idx"),
            models.Index(fields=["vin", "created_at"], name="integr_telem_vin_42f889_idx"),
            models.Index(fields=["external_event_id"], name="int_tel_ext_7f2a83_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.vin}: {self.mileage} км"
