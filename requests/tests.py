import json
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase

from accounts.models import Employee
from fleet.models import Car
from requests.models import Request
from requests.services import RequestServiceError, approve_request, assign_car

User = get_user_model()


class RequestServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="actor", password="pw")
        self.employee = Employee.objects.create(user=self.user, full_name="Actor")
        self.car = Car.objects.create(
            brand_model="Test",
            vin="1HGBH41JXMN109186",
            status=Car.Status.AVAILABLE,
        )
        self.req = Request.objects.create(
            employee=self.employee,
            reason="service",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=1),
            status=Request.Status.PENDING,
        )

    def test_approve_request_sets_approved(self):
        approve_request(req=self.req, actor=self.user)
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, Request.Status.APPROVED)

    def test_approve_completed_raises(self):
        self.req.status = Request.Status.COMPLETED
        self.req.save(update_fields=["status"])
        with self.assertRaises(RequestServiceError):
            approve_request(req=self.req, actor=self.user)

    def test_assign_car_only_when_approved(self):
        with self.assertRaises(RequestServiceError):
            assign_car(req=self.req, car=self.car, actor=self.user)


class RequestAPITests(TestCase):
    def setUp(self):
        self.employee_group, _ = Group.objects.get_or_create(name="employee")
        self.service_group, _ = Group.objects.get_or_create(name="service_admin")

        self.user1 = User.objects.create_user(username="emp1", password="pw1")
        self.user1.groups.add(self.employee_group)
        self.emp1 = Employee.objects.create(user=self.user1, full_name="Employee One")

        self.user2 = User.objects.create_user(username="emp2", password="pw2")
        self.user2.groups.add(self.employee_group)
        self.emp2 = Employee.objects.create(user=self.user2, full_name="Employee Two")

        self.admin = User.objects.create_user(username="svc", password="pwa")
        self.admin.groups.add(self.service_group)

        start = date.today()
        end = start + timedelta(days=1)
        self.r1 = Request.objects.create(
            employee=self.emp1,
            reason="r1",
            start_date=start,
            end_date=end,
        )
        self.r2 = Request.objects.create(
            employee=self.emp2,
            reason="r2",
            start_date=start,
            end_date=end,
        )

    def test_employee_sees_only_own_requests(self):
        client = Client()
        client.force_login(self.user1)
        res = client.get("/api/requests/", HTTP_ACCEPT="application/json")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.content)
        ids = {row["id"] for row in data["results"]}
        self.assertEqual(ids, {self.r1.id})

    def test_service_admin_sees_all_requests(self):
        client = Client()
        client.force_login(self.admin)
        res = client.get("/api/requests/", HTTP_ACCEPT="application/json")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.content)
        ids = {row["id"] for row in data["results"]}
        self.assertEqual(ids, {self.r1.id, self.r2.id})

    def test_obtain_auth_token(self):
        client = Client()
        res = client.post(
            "/api/auth/token/",
            data=json.dumps({"username": "emp1", "password": "pw1"}),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.content)
        self.assertIn("token", data)
