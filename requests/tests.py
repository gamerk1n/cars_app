import json
from io import StringIO
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from accounts.models import Employee
from audit.models import ActionLog
from fleet.models import Car, MaintenanceRecord
from requests.automation import run_request_automations
from requests.models import Reservation, Request, VehicleInspection, VehicleInspectionPhoto
from requests.notifications import notify_request_event, request_notification_recipients
from requests.services import (
    RequestServiceError,
    approve_request,
    assign_car,
    auto_assign_car,
    available_cars_for_request,
    complete_request,
    complete_request_with_inspection,
    create_vehicle_inspection,
    evaluate_auto_approval,
    inspection_defects_summary,
    process_auto_approval,
)

User = get_user_model()


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    NOTIFICATIONS_ENABLED=True,
    NOTIFICATIONS_EMAIL_ENABLED=True,
    NOTIFICATIONS_WEBHOOK_URL="",
    DEFAULT_FROM_EMAIL="fleet@example.com",
)
class RequestServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="actor",
            password="pw",
            email="employee@example.com",
        )
        self.employee = Employee.objects.create(
            user=self.user,
            full_name="Actor",
            email="employee-profile@example.com",
        )
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
            rules_accepted=True,
            rules_accepted_at=timezone.now(),
        )

    def create_reservation_request(self, *, car=None, start_date=None, end_date=None):
        car = car or self.car
        start_date = start_date or date.today()
        end_date = end_date or date.today() + timedelta(days=1)
        req = Request.objects.create(
            employee=self.employee,
            reason="reserved",
            start_date=start_date,
            end_date=end_date,
            status=Request.Status.APPROVED,
            car=car,
        )
        Reservation.objects.create(
            request=req,
            car=car,
            employee=self.employee,
            start_date=start_date,
            end_date=end_date,
        )
        return req

    def test_approve_request_sets_approved(self):
        approve_request(req=self.req, actor=self.user)
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, Request.Status.APPROVED)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["employee-profile@example.com"])

    def test_approve_completed_raises(self):
        self.req.status = Request.Status.COMPLETED
        self.req.save(update_fields=["status"])
        with self.assertRaises(RequestServiceError):
            approve_request(req=self.req, actor=self.user)

    def test_assign_car_only_when_approved(self):
        with self.assertRaises(RequestServiceError):
            assign_car(req=self.req, car=self.car, actor=self.user)

    def test_available_cars_excludes_overlapping_assignments(self):
        self.create_reservation_request(
            start_date=date.today() + timedelta(days=2),
            end_date=date.today() + timedelta(days=4),
        )
        backup = Car.objects.create(
            brand_model="Backup",
            vin="1HGBH41JXMN109187",
            status=Car.Status.AVAILABLE,
        )
        overlapping_req = Request.objects.create(
            employee=self.employee,
            reason="overlap",
            start_date=date.today() + timedelta(days=3),
            end_date=date.today() + timedelta(days=5),
            status=Request.Status.APPROVED,
        )

        candidates = list(available_cars_for_request(overlapping_req))

        self.assertEqual(candidates, [backup])

    def test_available_cars_excludes_service_due_cars(self):
        self.car.next_service_date = date.today()
        self.car.save(update_fields=["next_service_date"])
        backup = Car.objects.create(
            brand_model="Backup",
            vin="1HGBH41JXMN109195",
            status=Car.Status.AVAILABLE,
        )
        approve_request(req=self.req, actor=self.user)

        candidates = list(available_cars_for_request(self.req))

        self.assertEqual(candidates, [backup])

    def test_assign_car_rejects_service_due_car(self):
        self.car.current_mileage = 20000
        self.car.next_service_mileage = 20000
        self.car.save(update_fields=["current_mileage", "next_service_mileage"])
        approve_request(req=self.req, actor=self.user)

        with self.assertRaises(RequestServiceError):
            assign_car(req=self.req, car=self.car, actor=self.user)

    def test_assign_car_rejects_overlapping_assignment(self):
        self.create_reservation_request(
            start_date=date.today(),
            end_date=date.today() + timedelta(days=2),
        )
        approve_request(req=self.req, actor=self.user)

        with self.assertRaises(RequestServiceError):
            assign_car(req=self.req, car=self.car, actor=self.user)

    def test_assign_car_allows_non_overlapping_reservations(self):
        self.create_reservation_request(
            start_date=date.today() + timedelta(days=5),
            end_date=date.today() + timedelta(days=6),
        )
        approve_request(req=self.req, actor=self.user)

        assign_car(req=self.req, car=self.car, actor=self.user)

        self.req.refresh_from_db()
        self.car.refresh_from_db()
        self.assertEqual(self.req.car, self.car)
        self.assertEqual(self.car.status, Car.Status.ASSIGNED)
        self.assertEqual(
            Reservation.objects.filter(car=self.car, status=Reservation.Status.ACTIVE).count(),
            2,
        )

    def test_auto_assign_car_picks_available_candidate(self):
        self.create_reservation_request(
            start_date=date.today(),
            end_date=date.today() + timedelta(days=2),
        )
        backup = Car.objects.create(
            brand_model="Backup",
            vin="1HGBH41JXMN109188",
            status=Car.Status.AVAILABLE,
        )
        approve_request(req=self.req, actor=self.user)

        auto_assign_car(req=self.req, actor=self.user)

        self.req.refresh_from_db()
        backup.refresh_from_db()
        self.assertEqual(self.req.car, backup)
        self.assertEqual(backup.status, Car.Status.ASSIGNED)
        self.assertTrue(
            Reservation.objects.filter(request=self.req, car=backup).exists()
        )
        self.assertEqual(mail.outbox[-1].to, ["employee-profile@example.com"])

    def test_create_vehicle_inspection_records_issue_checklist_and_photos(self):
        approve_request(req=self.req, actor=self.user)
        assign_car(req=self.req, car=self.car, actor=self.user)
        photo = SimpleUploadedFile("body.jpg", b"image", content_type="image/jpeg")

        inspection = create_vehicle_inspection(
            req=self.req,
            kind=VehicleInspection.Kind.ISSUE,
            actor=self.user,
            data={
                "mileage": 12000,
                "fuel_level": 80,
                "exterior_condition": "Clean",
                "interior_condition": "Clean",
                "damage_zones": [],
                "defects": "",
                "employee_signature": "Actor",
                "inspector_signature": "Manager",
            },
            photo_files=[(VehicleInspectionPhoto.Label.EXTERIOR, photo)],
        )

        self.assertEqual(inspection.kind, VehicleInspection.Kind.ISSUE)
        self.assertEqual(inspection.request, self.req)
        self.assertEqual(inspection.photos.count(), 1)
        self.assertEqual(inspection.photos.get().original_name, "body.jpg")
        self.car.refresh_from_db()
        self.assertEqual(self.car.current_mileage, 12000)

    def test_complete_request_with_inspection_creates_repair_from_damage_zones(self):
        approve_request(req=self.req, actor=self.user)
        assign_car(req=self.req, car=self.car, actor=self.user)

        req, inspection = complete_request_with_inspection(
            req=self.req,
            actor=self.user,
            inspection_data={
                "mileage": 12100,
                "fuel_level": 60,
                "exterior_condition": "Scratch",
                "interior_condition": "Clean",
                "damage_zones": ["front", "glass"],
                "defects": "Scratch on bumper",
                "employee_signature": "Actor",
                "inspector_signature": "Manager",
            },
        )

        req.refresh_from_db()
        self.car.refresh_from_db()
        self.assertEqual(req.status, Request.Status.COMPLETED)
        self.assertEqual(inspection.kind, VehicleInspection.Kind.RETURN)
        self.assertIn("Scratch on bumper", req.return_defects)
        self.assertIn("Зоны повреждений", req.return_defects)
        self.assertEqual(self.car.status, Car.Status.MAINTENANCE)
        self.assertEqual(MaintenanceRecord.objects.get(car=self.car).description, req.return_defects)

    def test_inspection_defects_summary_uses_damage_zones_without_defect_text(self):
        approve_request(req=self.req, actor=self.user)
        assign_car(req=self.req, car=self.car, actor=self.user)
        inspection = create_vehicle_inspection(
            req=self.req,
            kind=VehicleInspection.Kind.RETURN,
            actor=self.user,
            data={
                "mileage": 12100,
                "fuel_level": 60,
                "exterior_condition": "",
                "interior_condition": "",
                "damage_zones": ["wheels"],
                "defects": "",
                "employee_signature": "Actor",
                "inspector_signature": "Manager",
            },
        )

        self.assertIn("Колёса", inspection_defects_summary(inspection))

    def test_process_auto_approval_approves_and_assigns_clean_request(self):
        process_auto_approval(req=self.req, actor=self.user)

        self.req.refresh_from_db()
        self.car.refresh_from_db()
        self.assertEqual(self.req.status, Request.Status.APPROVED)
        self.assertEqual(self.req.car, self.car)
        self.assertEqual(self.car.status, Car.Status.ASSIGNED)

    def test_evaluate_auto_approval_requires_rules_acceptance(self):
        self.req.rules_accepted = False
        self.req.save(update_fields=["rules_accepted"])

        decision = evaluate_auto_approval(self.req)

        self.assertFalse(decision.approved)
        self.assertIn("сотрудник не подтвердил правила", decision.reasons)

    def test_process_auto_approval_blocks_employee_date_conflict(self):
        Request.objects.create(
            employee=self.employee,
            reason="service",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=1),
            status=Request.Status.PENDING,
        )

        _req, decision = process_auto_approval(req=self.req, actor=self.user)

        self.req.refresh_from_db()
        self.car.refresh_from_db()
        self.assertFalse(decision.approved)
        self.assertEqual(self.req.status, Request.Status.PENDING)
        self.assertIsNone(self.req.car)
        self.assertEqual(self.car.status, Car.Status.AVAILABLE)

    def test_complete_request_marks_car_available_without_defects(self):
        approve_request(req=self.req, actor=self.user)
        assign_car(req=self.req, car=self.car, actor=self.user)

        complete_request(req=self.req, actor=self.user, defects="")

        self.req.refresh_from_db()
        self.car.refresh_from_db()
        self.assertEqual(self.req.status, Request.Status.COMPLETED)
        self.assertEqual(self.car.status, Car.Status.AVAILABLE)

    def test_complete_request_marks_car_maintenance_with_defects(self):
        approve_request(req=self.req, actor=self.user)
        assign_car(req=self.req, car=self.car, actor=self.user)

        complete_request(req=self.req, actor=self.user, defects="Скол на двери")

        self.req.refresh_from_db()
        self.car.refresh_from_db()
        self.assertEqual(self.req.status, Request.Status.COMPLETED)
        self.assertEqual(self.req.return_defects, "Скол на двери")
        self.assertEqual(self.car.status, Car.Status.MAINTENANCE)
        record = MaintenanceRecord.objects.get(car=self.car)
        self.assertEqual(record.kind, MaintenanceRecord.Kind.REPAIR)
        self.assertEqual(record.request, self.req)
        self.assertEqual(record.description, self.req.return_defects)
        recipients = [recipient for email in mail.outbox for recipient in email.to]
        self.assertIn("employee-profile@example.com", recipients)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    NOTIFICATIONS_ENABLED=True,
    NOTIFICATIONS_EMAIL_ENABLED=True,
    NOTIFICATIONS_WEBHOOK_URL="",
    DEFAULT_FROM_EMAIL="fleet@example.com",
)
class RequestAutomationTests(TestCase):
    def setUp(self):
        self.service_group, _ = Group.objects.get_or_create(name="service_admin")
        self.user = User.objects.create_user(
            username="actor",
            password="pw",
            email="employee@example.com",
        )
        self.employee = Employee.objects.create(
            user=self.user,
            full_name="Actor",
            email="employee-profile@example.com",
        )
        self.admin = User.objects.create_user(
            username="svc",
            password="pw",
            email="admin@example.com",
        )
        self.admin.groups.add(self.service_group)
        self.car = Car.objects.create(
            brand_model="Test",
            vin="1HGBH41JXMN209186",
            status=Car.Status.AVAILABLE,
        )

    def create_request(self, **kwargs):
        defaults = {
            "employee": self.employee,
            "reason": "service",
            "start_date": date.today(),
            "end_date": date.today() + timedelta(days=1),
            "status": Request.Status.PENDING,
            "rules_accepted": True,
            "rules_accepted_at": timezone.now(),
        }
        defaults.update(kwargs)
        return Request.objects.create(**defaults)

    def test_run_request_automations_marks_overdue_returns(self):
        req = self.create_request(
            start_date=date.today() - timedelta(days=3),
            end_date=date.today() - timedelta(days=1),
            status=Request.Status.APPROVED,
            car=self.car,
            assigned_at=timezone.now() - timedelta(days=3),
        )
        self.car.status = Car.Status.ASSIGNED
        self.car.save(update_fields=["status"])

        summary = run_request_automations(actor=self.user)

        req.refresh_from_db()
        self.assertEqual(summary.overdue_marked, 1)
        self.assertEqual(req.status, Request.Status.OVERDUE)
        recipients = {recipient for email in mail.outbox for recipient in email.to}
        self.assertEqual(recipients, {"employee-profile@example.com", "admin@example.com"})
        self.assertTrue(
            ActionLog.objects.filter(action="request.return_overdue", object_id=str(req.id)).exists()
        )

        complete_request(req=req, actor=self.user)
        req.refresh_from_db()
        self.car.refresh_from_db()
        self.assertEqual(req.status, Request.Status.COMPLETED)
        self.assertEqual(self.car.status, Car.Status.AVAILABLE)

    def test_run_request_automations_creates_return_reminder_once_per_day(self):
        req = self.create_request(
            end_date=date.today() + timedelta(days=1),
            status=Request.Status.APPROVED,
            car=self.car,
            assigned_at=timezone.now(),
        )
        self.car.status = Car.Status.ASSIGNED
        self.car.save(update_fields=["status"])

        first = run_request_automations(actor=self.user)
        second = run_request_automations(actor=self.user)

        self.assertEqual(first.return_reminders_created, 1)
        self.assertEqual(second.return_reminders_created, 0)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["employee-profile@example.com"])
        self.assertEqual(
            ActionLog.objects.filter(action="request.return_due_soon", object_id=str(req.id)).count(),
            1,
        )

    def test_run_request_automations_retries_auto_assignment(self):
        req = self.create_request(status=Request.Status.APPROVED)

        summary = run_request_automations(actor=self.user)

        req.refresh_from_db()
        self.car.refresh_from_db()
        self.assertEqual(summary.auto_assigned, 1)
        self.assertEqual(req.car, self.car)
        self.assertEqual(self.car.status, Car.Status.ASSIGNED)

    def test_run_request_automations_flags_stale_pending_once_per_day(self):
        req = self.create_request()
        Request.objects.filter(pk=req.pk).update(
            created_at=timezone.now() - timedelta(hours=25)
        )

        first = run_request_automations(actor=self.user)
        second = run_request_automations(actor=self.user)

        self.assertEqual(first.stale_pending_flagged, 1)
        self.assertEqual(second.stale_pending_flagged, 0)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["admin@example.com"])
        self.assertEqual(
            ActionLog.objects.filter(action="request.pending_stale", object_id=str(req.id)).count(),
            1,
        )

    def test_run_request_automations_marks_due_car_for_maintenance(self):
        self.car.next_service_date = date.today()
        self.car.save(update_fields=["next_service_date"])

        summary = run_request_automations(actor=self.user)

        self.car.refresh_from_db()
        self.assertEqual(summary.maintenance_due_marked, 1)
        self.assertEqual(self.car.status, Car.Status.MAINTENANCE)

    def test_run_request_automations_management_command_outputs_summary(self):
        out = StringIO()

        call_command("run_request_automations", stdout=out)

        self.assertIn("Request automations completed", out.getvalue())


class RequestAttachmentViewsTests(TestCase):
    def setUp(self):
        override = override_settings(
            STORAGES={
                "default": {
                    "BACKEND": "django.core.files.storage.InMemoryStorage",
                },
                "staticfiles": {
                    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
                },
            }
        )
        override.enable()
        self.addCleanup(override.disable)

        self.employee_group, _ = Group.objects.get_or_create(name="employee")
        self.client_group, _ = Group.objects.get_or_create(name="client")
        self.service_group, _ = Group.objects.get_or_create(name="service_admin")

        self.user = User.objects.create_user(username="emp", password="pw")
        self.user.groups.add(self.employee_group)
        self.employee = Employee.objects.create(user=self.user, full_name="Employee")

        self.client_user = User.objects.create_user(username="client", password="pw")
        self.client_user.groups.add(self.client_group)
        self.client_employee = Employee.objects.create(user=self.client_user, full_name="Client")

        self.admin = User.objects.create_user(username="svc", password="pw")
        self.admin.groups.add(self.service_group)

    def test_employee_can_create_request_with_attachment_and_rules(self):
        client = Client()
        client.force_login(self.user)
        attachment = SimpleUploadedFile(
            "route.txt", b"route file", content_type="text/plain"
        )

        res = client.post(
            "/requests/new/",
            data={
                "start_date": date.today(),
                "end_date": date.today() + timedelta(days=1),
                "reason": "business trip",
                "attachment": attachment,
                "rules_accepted": "on",
            },
        )

        self.assertEqual(res.status_code, 302)
        req = Request.objects.get(reason="business trip")
        self.assertTrue(req.rules_accepted)
        self.assertIsNotNone(req.rules_accepted_at)
        self.assertEqual(req.attachment_original_name, "route.txt")
        self.assertTrue(req.attachment.name.startswith("request_attachments/"))

        client.force_login(self.admin)
        res = client.get(f"/requests/{req.id}/attachment/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(b"".join(res.streaming_content), b"route file")
        res.close()

    def test_client_can_create_request_with_attachment_and_rules(self):
        client = Client()
        client.force_login(self.client_user)
        attachment = SimpleUploadedFile(
            "client-route.txt", b"client route file", content_type="text/plain"
        )

        res = client.post(
            "/requests/new/",
            data={
                "start_date": date.today(),
                "end_date": date.today() + timedelta(days=1),
                "reason": "client trip",
                "attachment": attachment,
                "rules_accepted": "on",
            },
        )

        self.assertEqual(res.status_code, 302)
        req = Request.objects.get(reason="client trip")
        self.assertEqual(req.employee, self.client_employee)
        self.assertEqual(req.attachment_original_name, "client-route.txt")

    def test_create_request_requires_rules_acceptance(self):
        client = Client()
        client.force_login(self.user)

        res = client.post(
            "/requests/new/",
            data={
                "start_date": date.today(),
                "end_date": date.today() + timedelta(days=1),
                "reason": "business trip",
            },
        )

        self.assertEqual(res.status_code, 200)
        self.assertFalse(Request.objects.filter(reason="business trip").exists())

    def test_employee_auto_approval_on_create_when_rules_pass(self):
        car = Car.objects.create(
            brand_model="Auto",
            vin="1HGBH41JXMN109190",
            status=Car.Status.AVAILABLE,
        )
        client = Client()
        client.force_login(self.user)

        res = client.post(
            "/requests/new/",
            data={
                "start_date": date.today(),
                "end_date": date.today() + timedelta(days=1),
                "reason": "service",
                "rules_accepted": "on",
            },
        )

        self.assertEqual(res.status_code, 302)
        req = Request.objects.get(reason="service")
        car.refresh_from_db()
        self.assertEqual(req.status, Request.Status.APPROVED)
        self.assertEqual(req.car, car)
        self.assertEqual(car.status, Car.Status.ASSIGNED)
        self.assertTrue(
            Reservation.objects.filter(request=req, car=car, status=Reservation.Status.ACTIVE).exists()
        )

    def test_admin_creates_issue_inspection_from_ui(self):
        car = Car.objects.create(
            brand_model="Auto",
            vin="1HGBH41JXMN109193",
            status=Car.Status.ASSIGNED,
        )
        req = Request.objects.create(
            employee=self.employee,
            reason="service",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=1),
            status=Request.Status.APPROVED,
            car=car,
            assigned_at=timezone.now(),
        )
        client = Client()
        client.force_login(self.admin)

        res = client.post(
            f"/requests/admin/{req.id}/issue-inspection/",
            data={
                "mileage": "12000",
                "fuel_level": "75",
                "exterior_condition": "Clean",
                "interior_condition": "Clean",
                "employee_signature": "Employee",
                "inspector_signature": "Service",
            },
        )

        self.assertEqual(res.status_code, 302)
        inspection = VehicleInspection.objects.get(request=req, kind=VehicleInspection.Kind.ISSUE)
        self.assertEqual(inspection.mileage, 12000)

    def test_admin_return_inspection_completes_request_from_ui(self):
        car = Car.objects.create(
            brand_model="Auto",
            vin="1HGBH41JXMN109194",
            status=Car.Status.ASSIGNED,
        )
        req = Request.objects.create(
            employee=self.employee,
            reason="service",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=1),
            status=Request.Status.APPROVED,
            car=car,
            assigned_at=timezone.now(),
        )
        client = Client()
        client.force_login(self.admin)

        res = client.post(
            f"/requests/admin/{req.id}/return/",
            data={
                "mileage": "12100",
                "fuel_level": "55",
                "exterior_condition": "Scratch",
                "interior_condition": "Clean",
                "damage_zones": ["front"],
                "defects": "Scratch",
                "employee_signature": "Employee",
                "inspector_signature": "Service",
            },
        )

        self.assertEqual(res.status_code, 302)
        req.refresh_from_db()
        car.refresh_from_db()
        self.assertEqual(req.status, Request.Status.COMPLETED)
        self.assertEqual(car.status, Car.Status.MAINTENANCE)
        self.assertTrue(
            VehicleInspection.objects.filter(
                request=req,
                kind=VehicleInspection.Kind.RETURN,
            ).exists()
        )


class RequestAPITests(TestCase):
    def setUp(self):
        self.employee_group, _ = Group.objects.get_or_create(name="employee")
        self.client_group, _ = Group.objects.get_or_create(name="client")
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

    def test_client_role_sees_only_own_requests(self):
        client_user = User.objects.create_user(username="client", password="pw")
        client_user.groups.add(self.client_group)
        client_employee = Employee.objects.create(user=client_user, full_name="Client")
        client_request = Request.objects.create(
            employee=client_employee,
            reason="client",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=1),
        )

        client = Client()
        client.force_login(client_user)
        res = client.get("/api/requests/", HTTP_ACCEPT="application/json")

        self.assertEqual(res.status_code, 200)
        data = json.loads(res.content)
        ids = {row["id"] for row in data["results"]}
        self.assertEqual(ids, {client_request.id})

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

    def test_service_admin_can_auto_assign_request(self):
        car = Car.objects.create(
            brand_model="Auto",
            vin="1HGBH41JXMN109189",
            status=Car.Status.AVAILABLE,
        )
        self.r1.status = Request.Status.APPROVED
        self.r1.save(update_fields=["status"])
        client = Client()
        client.force_login(self.admin)

        res = client.post(
            f"/api/requests/{self.r1.id}/auto_assign/",
            HTTP_ACCEPT="application/json",
        )

        self.assertEqual(res.status_code, 200)
        self.r1.refresh_from_db()
        car.refresh_from_db()
        self.assertEqual(self.r1.car, car)
        self.assertEqual(car.status, Car.Status.ASSIGNED)

    def test_service_admin_can_auto_approve_clean_request(self):
        car = Car.objects.create(
            brand_model="Auto",
            vin="1HGBH41JXMN109191",
            status=Car.Status.AVAILABLE,
        )
        self.r1.reason = "service"
        self.r1.rules_accepted = True
        self.r1.rules_accepted_at = timezone.now()
        self.r1.save(update_fields=["reason", "rules_accepted", "rules_accepted_at"])
        client = Client()
        client.force_login(self.admin)

        res = client.post(
            f"/api/requests/{self.r1.id}/auto_approve/",
            HTTP_ACCEPT="application/json",
        )

        self.assertEqual(res.status_code, 200)
        self.r1.refresh_from_db()
        car.refresh_from_db()
        self.assertEqual(self.r1.status, Request.Status.APPROVED)
        self.assertEqual(self.r1.car, car)
        self.assertEqual(car.status, Car.Status.ASSIGNED)

    def test_api_create_auto_approves_clean_request(self):
        car = Car.objects.create(
            brand_model="Auto",
            vin="1HGBH41JXMN109192",
            status=Car.Status.AVAILABLE,
        )
        start = date.today() + timedelta(days=10)
        end = start + timedelta(days=1)
        client = Client()
        client.force_login(self.user1)

        res = client.post(
            "/api/requests/",
            data=json.dumps(
                {
                    "reason": "service",
                    "start_date": start.isoformat(),
                    "end_date": end.isoformat(),
                    "rules_accepted": True,
                }
            ),
            content_type="application/json",
            HTTP_ACCEPT="application/json",
        )

        self.assertEqual(res.status_code, 201)
        data = json.loads(res.content)
        req = Request.objects.get(pk=data["id"])
        car.refresh_from_db()
        self.assertEqual(req.status, Request.Status.APPROVED)
        self.assertEqual(req.car, car)
        self.assertEqual(car.status, Car.Status.AVAILABLE)
        self.assertTrue(
            Reservation.objects.filter(request=req, car=car, status=Reservation.Status.ACTIVE).exists()
        )

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
