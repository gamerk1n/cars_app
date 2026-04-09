from django.http import JsonResponse
from django.urls import include, path

from rest_framework.routers import DefaultRouter

from audit.api import ActionLogViewSet
from fleet.api import CarViewSet
from reports.api import ReportViewSet
from requests.api import RequestViewSet

router = DefaultRouter()
router.register("cars", CarViewSet, basename="car")
router.register("requests", RequestViewSet, basename="request")
router.register("reports", ReportViewSet, basename="report")
router.register("logs", ActionLogViewSet, basename="actionlog")

urlpatterns = [
    path("health/", lambda request: JsonResponse({"ok": True}), name="api_health"),
    path("", include(router.urls)),
]
