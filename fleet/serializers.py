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
            "created_at",
            "updated_at",
        ]
