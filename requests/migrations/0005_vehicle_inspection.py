import requests.models
import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
        ("fleet", "0002_maintenance_record"),
        ("requests", "0004_request_status_overdue"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="VehicleInspection",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "kind",
                    models.CharField(
                        choices=[("issue", "Выдача"), ("return", "Возврат")],
                        max_length=20,
                    ),
                ),
                ("mileage", models.PositiveIntegerField()),
                (
                    "fuel_level",
                    models.PositiveSmallIntegerField(
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(100),
                        ]
                    ),
                ),
                ("exterior_condition", models.TextField(blank=True)),
                ("interior_condition", models.TextField(blank=True)),
                ("damage_zones", models.JSONField(blank=True, default=list)),
                ("defects", models.TextField(blank=True)),
                ("employee_signature", models.CharField(max_length=160)),
                ("inspector_signature", models.CharField(max_length=160)),
                ("completed_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "car",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="inspections",
                        to="fleet.car",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="vehicle_inspections_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "employee",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="vehicle_inspections",
                        to="accounts.employee",
                    ),
                ),
                (
                    "request",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="inspections",
                        to="requests.request",
                    ),
                ),
            ],
            options={
                "ordering": ["-completed_at", "-created_at"],
                "indexes": [
                    models.Index(fields=["request", "kind"], name="requests_ve_request_7e2616_idx"),
                    models.Index(fields=["car", "kind"], name="requests_ve_car_id_34a4cd_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("request", "kind"),
                        name="unique_request_inspection_kind",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="VehicleInspectionPhoto",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "image",
                    models.FileField(upload_to=requests.models.inspection_photo_upload_to),
                ),
                (
                    "label",
                    models.CharField(
                        choices=[
                            ("exterior", "Кузов"),
                            ("interior", "Салон"),
                            ("damage", "Повреждения"),
                            ("other", "Другое"),
                        ],
                        default="other",
                        max_length=20,
                    ),
                ),
                ("original_name", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "inspection",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="photos",
                        to="requests.vehicleinspection",
                    ),
                ),
            ],
            options={
                "ordering": ["created_at", "id"],
            },
        ),
    ]
