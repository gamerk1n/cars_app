from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

from accounts.roles import CLIENT, EMPLOYEE, SERVICE_ADMIN, SYS_ADMIN, SYSTEM_ROLES


class Command(BaseCommand):
    help = "Create default groups and assign base permissions."

    def handle(self, *args, **options):
        employee_group, _ = Group.objects.get_or_create(name=EMPLOYEE)
        client_group, _ = Group.objects.get_or_create(name=CLIENT)
        service_admin_group, _ = Group.objects.get_or_create(name=SERVICE_ADMIN)
        sys_admin_group, _ = Group.objects.get_or_create(name=SYS_ADMIN)

        def perms(codenames: list[str]) -> list[Permission]:
            return list(Permission.objects.filter(codename__in=codenames))

        # Requester roles: create/view own requests (object-level filtering in views)
        requester_permissions = perms(
            [
                "add_request",
                "view_request",
            ]
        )
        employee_group.permissions.set(requester_permissions)
        client_group.permissions.set(requester_permissions)

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

        self.stdout.write(self.style.SUCCESS(f"Groups created/updated: {', '.join(SYSTEM_ROLES)}"))
