from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.permissions import IsEmployee, IsServiceAdmin
from requests.models import Request
from requests.notifications import notify_request_event
from requests.serializers import AssignCarSerializer, RequestSerializer
from requests.services import (
    RequestServiceError,
    approve_request,
    assign_car,
    auto_assign_car,
    complete_request,
    process_auto_approval,
    reject_request,
    set_pending,
)


class RequestViewSet(viewsets.ModelViewSet):
    serializer_class = RequestSerializer
    permission_classes = [IsEmployee]
    filterset_fields = ["status", "start_date", "end_date", "car"]
    search_fields = ["reason", "employee__full_name", "car__vin", "car__brand_model"]
    ordering_fields = ["created_at", "start_date", "end_date", "status"]

    def get_queryset(self):
        qs = Request.objects.select_related("employee", "car").all()
        user = self.request.user
        if user.is_superuser or user.groups.filter(name="sys_admin").exists():
            return qs
        if user.groups.filter(name="service_admin").exists():
            return qs
        return qs.filter(employee__user=user)

    def perform_create(self, serializer):
        req = serializer.save()
        notify_request_event("created", req, actor=self.request.user)
        req, _decision = process_auto_approval(req=req, actor=self.request.user)
        serializer.instance = req

    @action(detail=True, methods=["post"], permission_classes=[IsServiceAdmin])
    def approve(self, request, pk=None):
        req = self.get_object()
        try:
            approve_request(req=req, actor=request.user)
        except RequestServiceError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(RequestSerializer(req, context={"request": request}).data)

    @action(detail=True, methods=["post"], permission_classes=[IsServiceAdmin])
    def reject(self, request, pk=None):
        req = self.get_object()
        try:
            reject_request(req=req, actor=request.user, reason=request.data.get("reason"))
        except RequestServiceError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(RequestSerializer(req, context={"request": request}).data)

    @action(detail=True, methods=["post"], permission_classes=[IsServiceAdmin])
    def pending(self, request, pk=None):
        req = self.get_object()
        try:
            set_pending(req=req, actor=request.user)
        except RequestServiceError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(RequestSerializer(req, context={"request": request}).data)

    @action(detail=True, methods=["post"], permission_classes=[IsServiceAdmin])
    def assign(self, request, pk=None):
        req = self.get_object()
        serializer = AssignCarSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        car = serializer.validated_data["car"]
        try:
            assign_car(req=req, car=car, actor=request.user)
        except RequestServiceError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(RequestSerializer(req, context={"request": request}).data)

    @action(detail=True, methods=["post"], permission_classes=[IsServiceAdmin])
    def auto_assign(self, request, pk=None):
        req = self.get_object()
        try:
            auto_assign_car(req=req, actor=request.user)
        except RequestServiceError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(RequestSerializer(req, context={"request": request}).data)

    @action(detail=True, methods=["post"], permission_classes=[IsServiceAdmin])
    def auto_approve(self, request, pk=None):
        req = self.get_object()
        try:
            req, decision = process_auto_approval(req=req, actor=request.user)
        except RequestServiceError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        if not decision.approved:
            return Response(
                {"detail": "Автоодобрение недоступно.", "reasons": decision.reasons},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(RequestSerializer(req, context={"request": request}).data)

    @action(detail=True, methods=["post"], permission_classes=[IsServiceAdmin])
    def complete(self, request, pk=None):
        req = self.get_object()
        try:
            complete_request(req=req, actor=request.user, defects=request.data.get("defects"))
        except RequestServiceError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(RequestSerializer(req, context={"request": request}).data)
