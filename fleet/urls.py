from django.urls import path

from fleet import views

urlpatterns = [
    path("admin/", views.admin_cars, name="admin_cars"),
    path("admin/new/", views.admin_car_create, name="admin_car_create"),
    path("admin/<int:pk>/edit/", views.admin_car_edit, name="admin_car_edit"),
]
