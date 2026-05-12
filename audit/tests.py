from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import Employee
from audit.models import ActionLog
from audit.services import log_action
from fleet.models import Car
from requests.models import Request

User = get_user_model()


class ActionLogEventTests(TestCase):
    def setUp(self):
        self.sys_admin_group, _ = Group.objects.get_or_create(name="sys_admin")
        self.admin = User.objects.create_user(username="admin", password="pw")
        self.admin.groups.add(self.sys_admin_group)

        self.employee_user = User.objects.create_user(username="employee", password="pw")
        self.employee = Employee.objects.create(
            user=self.employee_user,
            full_name="Employee",
            email="employee@example.com",
        )
        self.car = Car.objects.create(
            brand_model="Test Car",
            vin="1HGBH41JXMN109186",
            status=Car.Status.AVAILABLE,
        )
        self.request = Request.objects.create(
            employee=self.employee,
            reason="service",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=1),
            status=Request.Status.APPROVED,
        )

    def test_log_action_enriches_known_request_event(self):
        log = log_action(
            actor=self.admin,
            action="request.assign_car",
            obj=self.request,
            payload={
                "car_id": str(self.car.id),
                "reservation_id": 10,
                "message": "Создана бронь на период заявки.",
            },
        )

        self.assertEqual(log.category, ActionLog.Category.RESERVATION)
        self.assertEqual(log.severity, ActionLog.Severity.INFO)
        self.assertEqual(log.title, "Автомобиль забронирован")
        self.assertEqual(log.message, "Создана бронь на период заявки.")
        self.assertEqual(log.request_id, self.request.id)
        self.assertEqual(log.car_id, self.car.id)
        self.assertEqual(log.object_type, "requests.request")
        self.assertEqual(log.actor, self.admin)

    def test_log_action_falls_back_to_object_context(self):
        log = log_action(
            actor=None,
            action="car.custom_check",
            obj=self.car,
            payload={"car_id": "not-a-number", "reason": "VIN сверка"},
        )

        self.assertEqual(log.category, ActionLog.Category.FLEET)
        self.assertEqual(log.severity, ActionLog.Severity.INFO)
        self.assertEqual(log.title, "car.custom_check")
        self.assertEqual(log.message, "car.custom_check: VIN сверка")
        self.assertIsNone(log.actor)
        self.assertIsNone(log.request_id)
        self.assertEqual(log.car_id, self.car.id)

    def test_sysadmin_logs_filter_business_events(self):
        reservation_log = log_action(
            actor=self.admin,
            action="request.assign_car",
            obj=self.request,
            payload={"car_id": self.car.id},
        )
        fleet_log = log_action(
            actor=self.admin,
            action="car.custom_check",
            obj=self.car,
            payload={"reason": "VIN сверка"},
        )

        client = Client()
        client.force_login(self.admin)
        response = client.get(
            reverse("sysadmin_logs"),
            {"category": "reservation", "severity": "info", "q": str(self.request.id)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reservation_log.title)
        self.assertContains(response, "Заявка #")
        self.assertNotContains(response, fleet_log.message)

    def test_action_log_api_returns_event_fields(self):
        log = log_action(
            actor=self.admin,
            action="request.assign_car",
            obj=self.request,
            payload={"car_id": self.car.id},
        )

        client = Client()
        client.force_login(self.admin)
        response = client.get("/api/logs/", {"category": "reservation"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        item = payload["results"][0]
        self.assertEqual(item["id"], log.id)
        self.assertEqual(item["category"], "reservation")
        self.assertEqual(item["category_display"], "Бронирования")
        self.assertEqual(item["severity"], "info")
        self.assertEqual(item["severity_display"], "Инфо")
        self.assertEqual(item["request_id"], self.request.id)
        self.assertEqual(item["car_id"], self.car.id)
