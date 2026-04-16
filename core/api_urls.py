from django.urls import include, path

from rest_framework.routers import DefaultRouter

from audit.api import ActionLogViewSet
from core.health import api_health, api_health_ready
from fleet.api import CarViewSet
from reports.api import ReportViewSet
from requests.api import RequestViewSet

router = DefaultRouter()
router.register("cars", CarViewSet, basename="car")
router.register("requests", RequestViewSet, basename="request")
router.register("reports", ReportViewSet, basename="report")
router.register("logs", ActionLogViewSet, basename="actionlog")

urlpatterns = [
    path("health/", api_health, name="api_health"),
    path("health/ready/", api_health_ready, name="api_health_ready"),
    path("", include(router.urls)),
]
