from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import Employee
from fleet.models import Car
from reports.calculations import calculate_fleet_metrics, calculate_report_usage
from reports.models import Report
from requests.models import Request, VehicleInspection

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
            current_mileage=1100,
            next_service_mileage=1300,
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
        VehicleInspection.objects.create(
            request=self.request_obj,
            car=self.car,
            employee=self.employee,
            kind=VehicleInspection.Kind.ISSUE,
            mileage=1000,
            fuel_level=80,
            employee_signature="Employee One",
            inspector_signature="Inspector",
        )
        VehicleInspection.objects.create(
            request=self.request_obj,
            car=self.car,
            employee=self.employee,
            kind=VehicleInspection.Kind.RETURN,
            mileage=1100,
            fuel_level=70,
            employee_signature="Employee One",
            inspector_signature="Inspector",
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
        self.assertContains(response, "Расчёты по заявке")
        self.assertContains(response, "100 км")
        self.assertContains(response, "50,0 км/день")

    def test_reports_list_contains_link_to_detail(self):
        client = Client()
        client.force_login(self.admin)

        response = client.get(reverse("admin_reports"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("admin_report_detail", args=[self.report.id]))
        self.assertContains(response, "Загрузка автопарка")
        self.assertContains(response, "100,0%")

    def test_report_usage_calculates_mileage_and_service_forecast(self):
        calculation = calculate_report_usage(self.report, today=date(2026, 1, 1))

        self.assertEqual(calculation.usage_days, 2)
        self.assertEqual(calculation.mileage_delta, 100)
        self.assertEqual(str(calculation.average_daily_mileage), "50.0")
        self.assertEqual(calculation.mileage_until_service, 200)
        self.assertEqual(calculation.service_forecast_days, 4)
        self.assertEqual(calculation.service_forecast_date, date(2026, 1, 5))

    def test_fleet_metrics_calculates_utilization(self):
        metrics = calculate_fleet_metrics(
            [self.report],
            total_cars=1,
            period_start=self.report.start_date,
            period_end=self.report.end_date,
        )

        self.assertEqual(metrics.period_days, 2)
        self.assertEqual(metrics.busy_car_days, 2)
        self.assertEqual(metrics.available_car_days, 2)
        self.assertEqual(str(metrics.utilization_percent), "100.0")
        self.assertEqual(metrics.total_mileage, 100)
        self.assertEqual(str(metrics.average_daily_mileage), "50.0")
