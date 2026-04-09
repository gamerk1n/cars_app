from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create default groups and assign base permissions."

    def handle(self, *args, **options):
        employee_group, _ = Group.objects.get_or_create(name="employee")
        service_admin_group, _ = Group.objects.get_or_create(name="service_admin")
        sys_admin_group, _ = Group.objects.get_or_create(name="sys_admin")

        def perms(codenames: list[str]) -> list[Permission]:
            return list(Permission.objects.filter(codename__in=codenames))

        # Employee: create/view own requests (object-level filtering in views)
        employee_group.permissions.set(
            perms(
                [
                    "add_request",
                    "view_request",
                ]
            )
        )

        # Service admin: manage requests + manage cars + view reports
        service_admin_group.permissions.set(
            perms(
                [
                    "view_request",
                    "change_request",
                    "add_car",
                    "view_car",
                    "change_car",
                    "view_report",
                    "add_report",
                ]
            )
        )

        # Sys admin: manage users/roles via UI (enforced by group checks)
        sys_admin_group.permissions.set(
            perms(
                [
                    "view_actionlog",
                ]
            )
        )

        self.stdout.write(self.style.SUCCESS("Groups created/updated: employee, service_admin, sys_admin"))
