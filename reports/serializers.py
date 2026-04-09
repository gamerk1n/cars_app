from rest_framework import serializers

from reports.models import Report


class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = [
            "id",
            "name",
            "request",
            "car",
            "employee",
            "start_date",
            "end_date",
            "created_at",
        ]
