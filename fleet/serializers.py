from rest_framework import serializers

from fleet.models import Car


class CarSerializer(serializers.ModelSerializer):
    class Meta:
        model = Car
        fields = [
            "id",
            "brand_model",
            "vin",
            "color",
            "type",
            "status",
            "current_mileage",
            "next_service_date",
            "next_service_mileage",
            "created_at",
            "updated_at",
        ]
