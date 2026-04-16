from rest_framework import serializers

from accounts.models import Employee
from fleet.models import Car
from requests.models import Request


class RequestSerializer(serializers.ModelSerializer):
    employee_id = serializers.IntegerField(source="employee.id", read_only=True)
    car_id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = Request
        fields = [
            "id",
            "reason",
            "start_date",
            "end_date",
            "status",
            "employee_id",
            "car_id",
            "assigned_at",
            "returned_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["status", "assigned_at", "returned_at", "created_at", "updated_at"]

    def validate(self, attrs):
        start_date = attrs.get("start_date") or getattr(self.instance, "start_date", None)
        end_date = attrs.get("end_date") or getattr(self.instance, "end_date", None)
        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError({"end_date": "Дата окончания должна быть не раньше даты начала."})
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        user = request.user
        try:
            employee: Employee = user.employee
        except Employee.DoesNotExist:
            raise serializers.ValidationError("Для пользователя не создан профиль Employee.")
        validated_data["employee"] = employee
        validated_data.pop("car", None)
        validated_data.pop("status", None)
        return super().create(validated_data)


class AssignCarSerializer(serializers.Serializer):
    car_id = serializers.PrimaryKeyRelatedField(queryset=Car.objects.all(), source="car")
