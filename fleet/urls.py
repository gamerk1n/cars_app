from django.urls import path

from fleet import views

urlpatterns = [
    path("admin/", views.admin_cars, name="admin_cars"),
    path("admin/new/", views.admin_car_create, name="admin_car_create"),
    path("admin/<int:pk>/qr.svg", views.admin_car_qr_svg, name="admin_car_qr_svg"),
    path("admin/<int:pk>/qr/", views.admin_car_qr_card, name="admin_car_qr_card"),
    path("admin/<int:pk>/edit/", views.admin_car_edit, name="admin_car_edit"),
    path("admin/<int:pk>/maintenance/", views.admin_car_maintenance, name="admin_car_maintenance"),
]
