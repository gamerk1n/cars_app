from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import Employee

User = get_user_model()


class SysadminUserTests(TestCase):
    def setUp(self):
        self.sys_admin_group, _ = Group.objects.get_or_create(name="sys_admin")
        self.employee_group, _ = Group.objects.get_or_create(name="employee")
        self.client_group, _ = Group.objects.get_or_create(name="client")

        self.admin = User.objects.create_user(username="admin", password="pw")
        self.admin.groups.add(self.sys_admin_group)

    def test_bootstrap_roles_creates_client_group_with_request_permissions(self):
        call_command("bootstrap_roles")

        client_group = Group.objects.get(name="client")
        permission_codenames = set(client_group.permissions.values_list("codename", flat=True))
        self.assertIn("add_request", permission_codenames)
        self.assertIn("view_request", permission_codenames)

    def test_dashboard_displays_localized_role_names(self):
        response = Client().get(reverse("sysadmin_dashboard"))
        self.assertEqual(response.status_code, 302)

        client = Client()
        client.force_login(self.admin)
        response = client.get(reverse("sysadmin_dashboard"))

        self.assertContains(response, "Сотрудник")
        self.assertContains(response, "Клиент")
        self.assertContains(response, "Администратор сервиса")
        self.assertContains(response, "Системный администратор")
        self.assertNotContains(response, "Employee")
        self.assertNotContains(response, "Service admin")
        self.assertNotContains(response, "Sys admin")

    def test_creates_employee_profile_for_employee_group(self):
        client = Client()
        client.force_login(self.admin)

        response = client.post(
            reverse("sysadmin_user_create"),
            {
                "username": "new_employee",
                "email": "employee@example.com",
                "full_name": "Иван Петров",
                "password": "pw12345",
                "is_active": "on",
                "groups": [self.employee_group.id],
            },
        )

        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username="new_employee")
        employee = Employee.objects.get(user=user)
        self.assertEqual(employee.full_name, "Иван Петров")
        self.assertEqual(employee.email, "employee@example.com")

    def test_creates_employee_profile_for_client_group(self):
        client = Client()
        client.force_login(self.admin)

        response = client.post(
            reverse("sysadmin_user_create"),
            {
                "username": "new_client",
                "email": "client@example.com",
                "full_name": "Мария Клиент",
                "password": "pw12345",
                "is_active": "on",
                "groups": [self.client_group.id],
            },
        )

        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username="new_client")
        employee = Employee.objects.get(user=user)
        self.assertEqual(employee.full_name, "Мария Клиент")
        self.assertEqual(employee.email, "client@example.com")

    def test_updates_employee_full_name_from_edit_form(self):
        user = User.objects.create_user(username="existing_employee", password="pw")
        user.groups.add(self.employee_group)
        Employee.objects.create(user=user, full_name="Старое Имя", email="old@example.com")

        client = Client()
        client.force_login(self.admin)

        response = client.post(
            reverse("sysadmin_user_edit", args=[user.id]),
            {
                "username": "existing_employee",
                "email": "new@example.com",
                "full_name": "Новое Имя",
                "is_active": "on",
                "groups": [self.employee_group.id],
            },
        )

        self.assertEqual(response.status_code, 302)
        employee = Employee.objects.get(user=user)
        self.assertEqual(employee.full_name, "Новое Имя")
        self.assertEqual(employee.email, "new@example.com")
