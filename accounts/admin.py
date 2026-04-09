from django.contrib import admin

from accounts.models import Employee


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("full_name", "position", "phone", "email", "user")
    search_fields = ("full_name", "phone", "email", "user__username")
