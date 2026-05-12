from rest_framework import serializers


class TelematicsMileageSerializer(serializers.Serializer):
    vin = serializers.CharField(max_length=17)
    mileage = serializers.IntegerField(min_value=0)
    recorded_at = serializers.DateTimeField(required=False)
    source = serializers.CharField(max_length=80, required=False, allow_blank=True)
    external_event_id = serializers.CharField(
        max_length=120,
        required=False,
        allow_blank=True,
    )
