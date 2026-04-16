from django.urls import path

from reports import views

urlpatterns = [
    path("admin/", views.admin_reports, name="admin_reports"),
    path("admin/<int:pk>/", views.admin_report_detail, name="admin_report_detail"),
]
