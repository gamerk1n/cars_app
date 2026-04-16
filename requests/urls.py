from django.urls import path

from requests import views

urlpatterns = [
    path("", views.employee_requests, name="employee_requests"),
    path("dashboard/", views.employee_dashboard, name="employee_dashboard"),
    path("new/", views.employee_request_create, name="employee_request_create"),
    path("admin/dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("admin/", views.admin_requests, name="admin_requests"),
    path("admin/<int:pk>/approve/", views.admin_request_approve, name="admin_request_approve"),
    path("admin/<int:pk>/reject/", views.admin_request_reject, name="admin_request_reject"),
    path("admin/<int:pk>/pending/", views.admin_request_pending, name="admin_request_pending"),
    path("admin/<int:pk>/assign/", views.admin_request_assign, name="admin_request_assign"),
    path("admin/<int:pk>/return/", views.admin_request_return, name="admin_request_return"),
]
