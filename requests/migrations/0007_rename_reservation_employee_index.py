from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("requests", "0006_reservation"),
    ]

    operations = [
        migrations.RenameIndex(
            model_name="reservation",
            old_name="requests_re_employee_2ea67b_idx",
            new_name="req_res_emp_2ea67b_idx",
        ),
    ]
