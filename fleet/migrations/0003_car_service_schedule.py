from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("fleet", "0002_maintenance_record"),
    ]

    operations = [
        migrations.AddField(
            model_name="car",
            name="current_mileage",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="car",
            name="next_service_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="car",
            name="next_service_mileage",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name="car",
            index=models.Index(fields=["next_service_date"], name="fleet_car_next_se_97e50b_idx"),
        ),
        migrations.AddIndex(
            model_name="car",
            index=models.Index(fields=["next_service_mileage"], name="fleet_car_next_se_5f426f_idx"),
        ),
    ]
