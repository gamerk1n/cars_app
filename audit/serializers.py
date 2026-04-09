from rest_framework import serializers

from audit.models import ActionLog


class ActionLogSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source="actor.username", read_only=True)

    class Meta:
        model = ActionLog
        fields = [
            "id",
            "created_at",
            "actor_username",
            "action",
            "object_type",
            "object_id",
            "payload",
        ]
