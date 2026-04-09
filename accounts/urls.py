from django.urls import path

from accounts import views

urlpatterns = [
    path("dashboard/", views.sysadmin_dashboard, name="sysadmin_dashboard"),
    path("users/", views.sysadmin_users, name="sysadmin_users"),
    path("users/new/", views.sysadmin_user_create, name="sysadmin_user_create"),
    path("users/<int:pk>/edit/", views.sysadmin_user_edit, name="sysadmin_user_edit"),
    path("users/<int:pk>/delete/", views.sysadmin_user_delete, name="sysadmin_user_delete"),
    path("logs/", views.sysadmin_logs, name="sysadmin_logs"),
]
