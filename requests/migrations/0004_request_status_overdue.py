from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("requests", "0003_request_attachment_rules"),
    ]

    operations = [
        migrations.AlterField(
            model_name="request",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Ожидание"),
                    ("approved", "Одобрена"),
                    ("rejected", "Отклонена"),
                    ("overdue", "Просрочена"),
                    ("completed", "Завершена"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
    ]
