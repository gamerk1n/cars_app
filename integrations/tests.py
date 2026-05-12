import json

from django.test import Client, TestCase, override_settings
from django.utils import timezone

from audit.models import ActionLog
from fleet.models import Car
from integrations.models import IntegrationEvent, TelematicsReading
from integrations.outbox import dispatch_pending_events


@override_settings(
    INTEGRATIONS_API_TOKEN="secret",
    INTEGRATIONS_OUTBOX_ENABLED=True,
    INTEGRATIONS_WEBHOOK_URL="",
)
class TelematicsIntegrationTests(TestCase):
    def setUp(self):
        self.car = Car.objects.create(
            brand_model="Telemetry Car",
            vin="1HGBH41JXMN109186",
            status=Car.Status.AVAILABLE,
            current_mileage=900,
            next_service_mileage=1000,
        )

    def post_mileage(self, payload, *, token="secret"):
        return Client().post(
            "/api/integrations/telematics/mileage/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_INTEGRATION_TOKEN=token,
        )

    def test_telematics_updates_mileage_marks_maintenance_and_enqueues_events(self):
        response = self.post_mileage(
            {
                "vin": self.car.vin.lower(),
                "mileage": 1000,
                "recorded_at": timezone.now().isoformat(),
                "source": "gps",
                "external_event_id": "evt-1",
            }
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["accepted"])
        self.assertTrue(body["maintenance_marked"])

        self.car.refresh_from_db()
        self.assertEqual(self.car.current_mileage, 1000)
        self.assertEqual(self.car.status, Car.Status.MAINTENANCE)

        reading = TelematicsReading.objects.get()
        self.assertTrue(reading.accepted)
        self.assertEqual(reading.source, "gps")

        mileage_log = ActionLog.objects.get(action="car.telematics_mileage")
        maintenance_log = ActionLog.objects.get(action="car.maintenance_due")
        self.assertEqual(mileage_log.car_id, self.car.id)
        self.assertEqual(maintenance_log.category, ActionLog.Category.MAINTENANCE)

        events = IntegrationEvent.objects.filter(
            action_log__action__in=["car.telematics_mileage", "car.maintenance_due"]
        )
        self.assertEqual(events.count(), 2)
        self.assertTrue(
            events.filter(
                event_type="car.telematics_mileage",
                payload__payload__external_event_id="evt-1",
            ).exists()
        )

    def test_telematics_ignores_lower_mileage_without_decreasing_car(self):
        self.car.current_mileage = 1200
        self.car.next_service_mileage = 2000
        self.car.save(update_fields=["current_mileage", "next_service_mileage"])

        response = self.post_mileage({"vin": self.car.vin, "mileage": 1100})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["accepted"])
        self.assertEqual(body["ignored_reason"], "Пробег не больше текущего значения")

        self.car.refresh_from_db()
        self.assertEqual(self.car.current_mileage, 1200)
        reading = TelematicsReading.objects.get()
        self.assertFalse(reading.accepted)
        self.assertEqual(reading.ignored_reason, "Пробег не больше текущего значения")

        log = ActionLog.objects.get(action="car.telematics_mileage_ignored")
        self.assertEqual(log.severity, ActionLog.Severity.WARNING)

    def test_telematics_rejects_invalid_token(self):
        response = self.post_mileage({"vin": self.car.vin, "mileage": 1000}, token="bad")

        self.assertEqual(response.status_code, 403)
        self.assertFalse(TelematicsReading.objects.exists())
        self.car.refresh_from_db()
        self.assertEqual(self.car.current_mileage, 900)

    @override_settings(INTEGRATIONS_API_TOKEN="")
    def test_telematics_endpoint_is_disabled_without_token(self):
        response = self.post_mileage({"vin": self.car.vin, "mileage": 1000})

        self.assertEqual(response.status_code, 503)
        self.assertFalse(TelematicsReading.objects.exists())

    def test_dispatch_without_webhook_is_noop(self):
        self.post_mileage({"vin": self.car.vin, "mileage": 950})

        summary = dispatch_pending_events()

        self.assertFalse(summary.configured)
        self.assertEqual(summary.sent, 0)
        self.assertTrue(IntegrationEvent.objects.filter(status=IntegrationEvent.Status.PENDING).exists())
