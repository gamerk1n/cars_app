import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def create_reservations_for_existing_requests(apps, schema_editor):
    request_model = apps.get_model("requests", "Request")
    reservation_model = apps.get_model("requests", "Reservation")
    for req in request_model.objects.filter(
        car_id__isnull=False,
        status__in=["approved", "overdue", "completed"],
    ):
        status = "completed" if req.status == "completed" else "active"
        completed_at = req.returned_at if status == "completed" else None
        reservation_model.objects.get_or_create(
            request_id=req.id,
            defaults={
                "car_id": req.car_id,
                "employee_id": req.employee_id,
                "start_date": req.start_date,
                "end_date": req.end_date,
                "status": status,
                "created_by_id": None,
                "completed_at": completed_at,
            },
        )


def delete_reservations(apps, schema_editor):
    reservation_model = apps.get_model("requests", "Reservation")
    reservation_model.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
        ("fleet", "0003_car_service_schedule"),
        ("requests", "0005_vehicle_inspection"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Reservation",
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
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("active", "Активна"),
                            ("cancelled", "Отменена"),
                            ("completed", "Завершена"),
                        ],
                        default="active",
                        max_length=20,
                    ),
                ),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "car",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="reservations",
                        to="fleet.car",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="reservations_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "employee",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="reservations",
                        to="accounts.employee",
                    ),
                ),
                (
                    "request",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reservation",
                        to="requests.request",
                    ),
                ),
            ],
            options={
                "ordering": ["start_date", "end_date", "id"],
                "indexes": [
                    models.Index(
                        fields=["car", "status", "start_date", "end_date"],
                        name="requests_re_car_id_9bbb5a_idx",
                    ),
                    models.Index(
                        fields=["employee", "status"],
                        name="requests_re_employee_2ea67b_idx",
                    ),
                    models.Index(fields=["status"], name="requests_re_status_b4c635_idx"),
                ],
            },
        ),
        migrations.RunPython(
            create_reservations_for_existing_requests,
            reverse_code=delete_reservations,
        ),
    ]
