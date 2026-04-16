from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import Employee

User = get_user_model()


class SysadminUserTests(TestCase):
    def setUp(self):
        self.sys_admin_group, _ = Group.objects.get_or_create(name="sys_admin")
        self.employee_group, _ = Group.objects.get_or_create(name="employee")

        self.admin = User.objects.create_user(username="admin", password="pw")
        self.admin.groups.add(self.sys_admin_group)

    def test_creates_employee_profile_for_employee_group(self):
        client = Client()
        client.force_login(self.admin)

        response = client.post(
            reverse("sysadmin_user_create"),
            {
                "username": "new_employee",
                "email": "employee@example.com",
                "password": "pw12345",
                "is_active": "on",
                "groups": [self.employee_group.id],
            },
        )

        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username="new_employee")
        employee = Employee.objects.get(user=user)
        self.assertEqual(employee.full_name, "new_employee")
        self.assertEqual(employee.email, "employee@example.com")
