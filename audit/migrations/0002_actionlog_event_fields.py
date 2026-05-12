from django.db import migrations, models


def as_positive_int(value):
    if value in (None, ""):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def backfill_event_fields(apps, schema_editor):
    action_log = apps.get_model("audit", "ActionLog")
    for log in action_log.objects.all().iterator():
        category = "system"
        severity = "info"
        if log.action.startswith("request.inspection"):
            category = "inspection"
        elif log.action.startswith("request.reservation"):
            category = "reservation"
        elif log.action.startswith("request."):
            category = "request"
        elif log.action.startswith("car.") or log.object_type.startswith("fleet."):
            category = "fleet"
        elif log.action.startswith("notification."):
            category = "notification"
        elif log.action.startswith("report."):
            category = "report"
        if any(marker in log.action for marker in ["blocked", "overdue", "stale", "reject"]):
            severity = "warning"
        if "error" in log.action:
            severity = "error"
        log.category = category
        log.severity = severity
        log.title = log.action.replace(".", " ")
        if log.object_type == "requests.request":
            log.request_id = as_positive_int(log.object_id)
        elif "request_id" in log.payload:
            log.request_id = as_positive_int(log.payload.get("request_id"))
        if "car_id" in log.payload:
            log.car_id = as_positive_int(log.payload.get("car_id"))
        elif log.object_type == "fleet.car":
            log.car_id = as_positive_int(log.object_id)
        log.save(
            update_fields=[
                "category",
                "severity",
                "title",
                "request_id",
                "car_id",
            ]
        )


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="actionlog",
            name="car_id",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="actionlog",
            name="category",
            field=models.CharField(
                choices=[
                    ("request", "Заявки"),
                    ("reservation", "Бронирования"),
                    ("fleet", "Автопарк"),
                    ("inspection", "Осмотры"),
                    ("maintenance", "ТО/ремонт"),
                    ("notification", "Уведомления"),
                    ("report", "Отчёты"),
                    ("security", "Безопасность"),
                    ("system", "Система"),
                ],
                default="system",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="actionlog",
            name="message",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="actionlog",
            name="request_id",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="actionlog",
            name="severity",
            field=models.CharField(
                choices=[
                    ("info", "Инфо"),
                    ("warning", "Предупреждение"),
                    ("error", "Ошибка"),
                ],
                default="info",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="actionlog",
            name="title",
            field=models.CharField(blank=True, max_length=160),
        ),
        migrations.AddIndex(
            model_name="actionlog",
            index=models.Index(
                fields=["category", "severity"],
                name="audit_actio_categor_99c6f2_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="actionlog",
            index=models.Index(
                fields=["request_id", "created_at"],
                name="audit_actio_request_a4603e_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="actionlog",
            index=models.Index(
                fields=["car_id", "created_at"],
                name="audit_actio_car_id_0bd8f8_idx",
            ),
        ),
        migrations.RunPython(backfill_event_fields, reverse_code=migrations.RunPython.noop),
    ]
