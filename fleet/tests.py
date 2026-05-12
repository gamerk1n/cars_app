from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.utils import timezone

from accounts.models import Employee
from audit.models import ActionLog
from fleet.models import Car, MaintenanceRecord
from fleet.qr import qr_svg
from fleet.services import mark_due_cars_for_maintenance, update_car_mileage
from requests.models import Reservation, Request

User = get_user_model()


class MaintenanceRecordViewsTests(TestCase):
    def setUp(self):
        self.service_group, _ = Group.objects.get_or_create(name="service_admin")
        self.user = User.objects.create_user(username="svc", password="pw")
        self.user.groups.add(self.service_group)
        self.car = Car.objects.create(
            brand_model="Test Car",
            vin="1HGBH41JXMN109186",
            status=Car.Status.AVAILABLE,
        )

    def test_service_admin_adds_maintenance_record(self):
        client = Client()
        client.force_login(self.user)

        res = client.post(
            f"/fleet/admin/{self.car.id}/maintenance/",
            data={
                "kind": MaintenanceRecord.Kind.SERVICE,
                "service_date": date.today(),
                "title": "Плановое ТО",
                "description": "Замена масла",
                "contractor": "Сервис",
                "mileage": "12000",
                "cost": "3500.00",
            },
        )

        self.assertEqual(res.status_code, 302)
        record = MaintenanceRecord.objects.get(car=self.car)
        self.assertEqual(record.kind, MaintenanceRecord.Kind.SERVICE)
        self.assertEqual(record.title, "Плановое ТО")
        self.assertEqual(record.created_by, self.user)

    def test_qr_svg_endpoint_returns_svg(self):
        client = Client()
        client.force_login(self.user)

        res = client.get(f"/fleet/admin/{self.car.id}/qr.svg")

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "image/svg+xml")
        self.assertIn(b"<svg", res.content)
        self.assertIn(b"<path", res.content)

    def test_qr_card_shows_active_request_actions(self):
        employee_user = User.objects.create_user(username="emp", password="pw")
        employee = Employee.objects.create(user=employee_user, full_name="Employee")
        self.car.status = Car.Status.ASSIGNED
        self.car.save(update_fields=["status"])
        req = Request.objects.create(
            employee=employee,
            reason="service",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=1),
            status=Request.Status.APPROVED,
            car=self.car,
            assigned_at=timezone.now(),
        )
        Reservation.objects.create(
            request=req,
            car=self.car,
            employee=employee,
            start_date=req.start_date,
            end_date=req.end_date,
        )
        client = Client()
        client.force_login(self.user)

        res = client.get(f"/fleet/admin/{self.car.id}/qr/")

        self.assertEqual(res.status_code, 200)
        self.assertContains(res, f"#{req.id}")
        self.assertContains(res, "Акт выдачи")
        self.assertContains(res, "Акт возврата")

    def test_qr_svg_helper_rejects_too_long_data(self):
        with self.assertRaises(ValueError):
            qr_svg("x" * 200)

    def test_maintenance_record_updates_car_mileage(self):
        client = Client()
        client.force_login(self.user)

        res = client.post(
            f"/fleet/admin/{self.car.id}/maintenance/",
            data={
                "kind": MaintenanceRecord.Kind.SERVICE,
                "service_date": date.today(),
                "title": "Service",
                "description": "",
                "contractor": "",
                "mileage": "15000",
                "cost": "",
            },
        )

        self.assertEqual(res.status_code, 302)
        self.car.refresh_from_db()
        self.assertEqual(self.car.current_mileage, 15000)

    def test_mark_due_cars_for_maintenance_by_date(self):
        self.car.next_service_date = date.today()
        self.car.save(update_fields=["next_service_date"])

        count = mark_due_cars_for_maintenance(actor=self.user)

        self.car.refresh_from_db()
        self.assertEqual(count, 1)
        self.assertEqual(self.car.status, Car.Status.MAINTENANCE)
        self.assertTrue(
            ActionLog.objects.filter(action="car.maintenance_due", object_id=str(self.car.id)).exists()
        )

    def test_mark_due_cars_for_maintenance_by_mileage(self):
        self.car.current_mileage = 20000
        self.car.next_service_mileage = 20000
        self.car.save(update_fields=["current_mileage", "next_service_mileage"])

        count = mark_due_cars_for_maintenance(actor=self.user)

        self.car.refresh_from_db()
        self.assertEqual(count, 1)
        self.assertEqual(self.car.status, Car.Status.MAINTENANCE)

    def test_update_car_mileage_does_not_decrease_value(self):
        self.car.current_mileage = 10000
        self.car.save(update_fields=["current_mileage"])

        changed = update_car_mileage(car=self.car, mileage=9000)

        self.car.refresh_from_db()
        self.assertFalse(changed)
        self.assertEqual(self.car.current_mileage, 10000)
