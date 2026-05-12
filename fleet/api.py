from rest_framework import viewsets

from core.permissions import IsServiceAdmin
from fleet.models import Car
from fleet.serializers import CarSerializer


class CarViewSet(viewsets.ModelViewSet):
    queryset = Car.objects.all()
    serializer_class = CarSerializer
    permission_classes = [IsServiceAdmin]
    filterset_fields = ["status", "type", "next_service_date"]
    search_fields = ["brand_model", "vin"]
    ordering_fields = [
        "brand_model",
        "vin",
        "status",
        "current_mileage",
        "next_service_date",
        "next_service_mileage",
        "updated_at",
    ]
