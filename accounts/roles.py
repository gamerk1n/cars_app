EMPLOYEE = "employee"
CLIENT = "client"
SERVICE_ADMIN = "service_admin"
SYS_ADMIN = "sys_admin"

REQUESTER_ROLES = (EMPLOYEE, CLIENT)
SYSTEM_ROLES = (EMPLOYEE, CLIENT, SERVICE_ADMIN, SYS_ADMIN)

ROLE_LABELS = {
    EMPLOYEE: "Сотрудник",
    CLIENT: "Клиент",
    SERVICE_ADMIN: "Администратор сервиса",
    SYS_ADMIN: "Системный администратор",
}


def role_label(role_name: str) -> str:
    return ROLE_LABELS.get(role_name, role_name)
