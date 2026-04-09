from rest_framework import mixins, viewsets

from core.permissions import IsServiceAdmin
from reports.models import Report
from reports.serializers import ReportSerializer


class ReportViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Report.objects.select_related("employee", "car", "request").all()
    serializer_class = ReportSerializer
    permission_classes = [IsServiceAdmin]
    filterset_fields = ["start_date", "end_date", "car", "employee"]
    search_fields = ["name", "car__vin", "car__brand_model", "employee__full_name"]
    ordering_fields = ["created_at", "start_date", "end_date"]
