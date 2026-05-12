from __future__ import annotations

import secrets

from django.conf import settings
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from fleet.models import Car
from integrations.serializers import TelematicsMileageSerializer
from integrations.services import ingest_telematics_mileage


class TelematicsMileageIngestView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        expected_token = getattr(settings, "INTEGRATIONS_API_TOKEN", "").strip()
        if not expected_token:
            return Response(
                {"detail": "Интеграционный токен не настроен."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        actual_token = request.headers.get("X-Integration-Token", "")
        if not secrets.compare_digest(actual_token, expected_token):
            return Response(
                {"detail": "Недействительный интеграционный токен."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = TelematicsMileageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            result = ingest_telematics_mileage(
                vin=data["vin"],
                mileage=data["mileage"],
                recorded_at=data.get("recorded_at"),
                source=data.get("source", ""),
                external_event_id=data.get("external_event_id", ""),
            )
        except Car.DoesNotExist:
            return Response(
                {"detail": "Автомобиль с таким VIN не найден."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "car_id": result.car_id,
                "vin": result.vin,
                "previous_mileage": result.previous_mileage,
                "mileage": result.mileage,
                "accepted": result.accepted,
                "ignored_reason": result.ignored_reason,
                "maintenance_marked": result.maintenance_marked,
                "car_status": result.car_status,
                "reading_id": result.reading_id,
            }
        )
