import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("audit", "0002_actionlog_event_fields"),
        ("fleet", "0003_car_service_schedule"),
    ]

    operations = [
        migrations.CreateModel(
            name="IntegrationEvent",
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
                ("event_type", models.CharField(max_length=100)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Ожидает"),
                            ("sent", "Отправлено"),
                            ("failed", "Ошибка"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("payload", models.JSONField(default=dict)),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("last_error", models.TextField(blank=True)),
                ("next_attempt_at", models.DateTimeField(blank=True, null=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "action_log",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="integration_event",
                        to="audit.actionlog",
                    ),
                ),
            ],
            options={
                "ordering": ["created_at", "id"],
                "indexes": [
                    models.Index(
                        fields=["status", "next_attempt_at"],
                        name="integr_event_status_f202c3_idx",
                    ),
                    models.Index(
                        fields=["event_type", "status"],
                        name="int_evt_type_e23c7c_idx",
                    ),
                    models.Index(fields=["created_at"], name="int_evt_created_8c25d7_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="TelematicsReading",
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
                ("vin", models.CharField(max_length=17)),
                ("mileage", models.PositiveIntegerField()),
                ("recorded_at", models.DateTimeField()),
                ("source", models.CharField(blank=True, max_length=80)),
                ("external_event_id", models.CharField(blank=True, max_length=120)),
                ("accepted", models.BooleanField(default=True)),
                ("ignored_reason", models.CharField(blank=True, max_length=160)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "car",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="telematics_readings",
                        to="fleet.car",
                    ),
                ),
            ],
            options={
                "ordering": ["-recorded_at", "-created_at"],
                "indexes": [
                    models.Index(
                        fields=["car", "recorded_at"],
                        name="integr_telem_car_id_bfda44_idx",
                    ),
                    models.Index(fields=["vin", "created_at"], name="integr_telem_vin_42f889_idx"),
                    models.Index(
                        fields=["external_event_id"],
                        name="int_tel_ext_7f2a83_idx",
                    ),
                ],
            },
        ),
    ]
