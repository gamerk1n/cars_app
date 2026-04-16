from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import Employee
from fleet.models import Car
from reports.models import Report
from requests.models import Request

User = get_user_model()


class ReportViewsTests(TestCase):
    def setUp(self):
        self.service_group, _ = Group.objects.get_or_create(name="service_admin")
        self.employee_group, _ = Group.objects.get_or_create(name="employee")

        self.admin = User.objects.create_user(username="svc", password="pw")
        self.admin.groups.add(self.service_group)

        self.user = User.objects.create_user(username="emp", password="pw2")
        self.user.groups.add(self.employee_group)
        self.employee = Employee.objects.create(
            user=self.user,
            full_name="Employee One",
            email="emp@example.com",
            phone="+70000000000",
        )

        self.car = Car.objects.create(
            brand_model="Test Car",
            vin="1HGBH41JXMN109186",
            status=Car.Status.AVAILABLE,
        )
        self.request_obj = Request.objects.create(
            employee=self.employee,
            car=self.car,
            reason="Командировка",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=1),
            status=Request.Status.COMPLETED,
            return_defects="Царапина на бампере",
        )
        self.report = Report.objects.create(
            name="Отчёт по заявке #1",
            request=self.request_obj,
            car=self.car,
            employee=self.employee,
            start_date=self.request_obj.start_date,
            end_date=self.request_obj.end_date,
        )

    def test_admin_can_open_report_detail(self):
        client = Client()
        client.force_login(self.admin)

        response = client.get(reverse("admin_report_detail", args=[self.report.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.report.name)
        self.assertContains(response, self.request_obj.reason)
        self.assertContains(response, self.request_obj.return_defects)

    def test_reports_list_contains_link_to_detail(self):
        client = Client()
        client.force_login(self.admin)

        response = client.get(reverse("admin_reports"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("admin_report_detail", args=[self.report.id]))
