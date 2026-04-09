from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Employee
from fleet.models import Car
from requests.models import Request
from requests.services import approve_request, assign_car, complete_request


User = get_user_model()


class Command(BaseCommand):
    help = "Seed demo data: users, employees, cars, requests."

    def handle(self, *args, **options):
        # Ensure groups exist
        for name in ["employee", "service_admin", "sys_admin"]:
            Group.objects.get_or_create(name=name)

        employee_group = Group.objects.get(name="employee")
        service_admin_group = Group.objects.get(name="service_admin")
        sys_admin_group = Group.objects.get(name="sys_admin")

        def upsert_user(username: str, password: str, groups: list[Group]):
            user, created = User.objects.get_or_create(username=username, defaults={"is_active": True})
            if created:
                user.set_password(password)
                user.save()
            user.groups.set(groups)
            return user

        employee_user = upsert_user("employee", "demo12345", [employee_group])
        service_admin_user = upsert_user("service_admin", "demo12345", [service_admin_group])
        sys_admin_user = upsert_user("sys_admin", "demo12345", [sys_admin_group])

        Employee.objects.get_or_create(
            user=employee_user,
            defaults={
                "full_name": "Иван Петров",
                "position": "Инженер",
                "phone": "+7 900 000-00-00",
                "email": "employee@example.com",
            },
        )
        Employee.objects.get_or_create(
            user=service_admin_user,
            defaults={
                "full_name": "Ольга Смирнова",
                "position": "Администратор сервиса",
                "phone": "+7 900 000-00-01",
                "email": "admin@example.com",
            },
        )
        Employee.objects.get_or_create(
            user=sys_admin_user,
            defaults={
                "full_name": "Сергей Иванов",
                "position": "Системный администратор",
                "phone": "+7 900 000-00-02",
                "email": "sysadmin@example.com",
            },
        )

        # Cars
        car1, _ = Car.objects.get_or_create(
            vin="JTNB11HK0J3000001",
            defaults={"brand_model": "Toyota Camry", "color": "Белый", "type": "Sedan", "status": Car.Status.AVAILABLE},
        )
        car2, _ = Car.objects.get_or_create(
            vin="TMBJJ7NE0L0000002",
            defaults={"brand_model": "Skoda Octavia", "color": "Серый", "type": "Sedan", "status": Car.Status.MAINTENANCE},
        )
        car3, _ = Car.objects.get_or_create(
            vin="WVGZZZ5NZJW000003",
            defaults={"brand_model": "Volkswagen Tiguan", "color": "Чёрный", "type": "SUV", "status": Car.Status.AVAILABLE},
        )

        employee = employee_user.employee
        today = timezone.localdate()

        # Requests
        pending_req, _ = Request.objects.get_or_create(
            employee=employee,
            reason="Ремонт личного авто",
            start_date=today,
            end_date=today,
            defaults={"status": Request.Status.PENDING},
        )

        approved_req, created = Request.objects.get_or_create(
            employee=employee,
            reason="ТО (плановое)",
            start_date=today,
            end_date=today,
            defaults={"status": Request.Status.PENDING},
        )
        if created or approved_req.status != Request.Status.APPROVED:
            approve_request(req=approved_req, actor=service_admin_user)
            assign_car(req=approved_req, car=car1 if car1.status == Car.Status.AVAILABLE else car3, actor=service_admin_user)

        completed_req, created = Request.objects.get_or_create(
            employee=employee,
            reason="ДТП (подменный авто на время ремонта)",
            start_date=today,
            end_date=today,
            defaults={"status": Request.Status.PENDING},
        )
        if created or completed_req.status != Request.Status.COMPLETED:
            approve_request(req=completed_req, actor=service_admin_user)
            assign_car(req=completed_req, car=car3 if car3.status == Car.Status.AVAILABLE else car1, actor=service_admin_user)
            complete_request(req=completed_req, actor=service_admin_user)

        self.stdout.write(self.style.SUCCESS("Seed complete. Login/password: employee/demo12345, service_admin/demo12345, sys_admin/demo12345"))
