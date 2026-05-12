from rest_framework import serializers

from audit.models import ActionLog


class ActionLogSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source="actor.username", read_only=True)
    category_display = serializers.CharField(source="get_category_display", read_only=True)
    severity_display = serializers.CharField(source="get_severity_display", read_only=True)

    class Meta:
        model = ActionLog
        fields = [
            "id",
            "created_at",
            "actor_username",
            "action",
            "category",
            "category_display",
            "severity",
            "severity_display",
            "title",
            "message",
            "request_id",
            "car_id",
            "object_type",
            "object_id",
            "payload",
        ]
