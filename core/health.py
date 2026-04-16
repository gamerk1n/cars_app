from django.conf import settings
from django.db import connection
from django.http import JsonResponse


def api_health(request):
    return JsonResponse({"ok": True})


def api_health_ready(request):
    try:
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception as exc:
        payload = {"ok": False, "database": "error"}
        if settings.DEBUG:
            payload["detail"] = str(exc)
        return JsonResponse(payload, status=503)
    return JsonResponse({"ok": True, "database": "ok"})
