from rest_framework import mixins, viewsets

from audit.models import ActionLog
from audit.serializers import ActionLogSerializer
from core.permissions import IsSysAdmin


class ActionLogViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = ActionLog.objects.select_related("actor").all()
    serializer_class = ActionLogSerializer
    permission_classes = [IsSysAdmin]
    filterset_fields = ["action", "object_type", "created_at"]
    search_fields = ["actor__username", "action", "object_type", "object_id"]
    ordering_fields = ["created_at"]
