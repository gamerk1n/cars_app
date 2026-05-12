from django.db import models
from django.conf import settings


class ActionLog(models.Model):
    class Category(models.TextChoices):
        REQUEST = "request", "Заявки"
        RESERVATION = "reservation", "Бронирования"
        FLEET = "fleet", "Автопарк"
        INSPECTION = "inspection", "Осмотры"
        MAINTENANCE = "maintenance", "ТО/ремонт"
        NOTIFICATION = "notification", "Уведомления"
        REPORT = "report", "Отчёты"
        SECURITY = "security", "Безопасность"
        SYSTEM = "system", "Система"

    class Severity(models.TextChoices):
        INFO = "info", "Инфо"
        WARNING = "warning", "Предупреждение"
        ERROR = "error", "Ошибка"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="action_logs",
    )
    action = models.CharField(max_length=80)
    object_type = models.CharField(max_length=80)
    object_id = models.CharField(max_length=64)
    category = models.CharField(
        max_length=30, choices=Category.choices, default=Category.SYSTEM
    )
    severity = models.CharField(
        max_length=20, choices=Severity.choices, default=Severity.INFO
    )
    title = models.CharField(max_length=160, blank=True)
    message = models.TextField(blank=True)
    request_id = models.PositiveIntegerField(null=True, blank=True)
    car_id = models.PositiveIntegerField(null=True, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_at"], name="audit_actio_created_a381fe_idx"),
            models.Index(fields=["action"], name="audit_actio_action_3f9ebe_idx"),
            models.Index(fields=["category", "severity"], name="audit_actio_categor_99c6f2_idx"),
            models.Index(fields=["request_id", "created_at"], name="audit_actio_request_a4603e_idx"),
            models.Index(fields=["car_id", "created_at"], name="audit_actio_car_id_0bd8f8_idx"),
            models.Index(fields=["object_type", "object_id"], name="audit_actio_object__b75c3c_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.action}"
