from django import template

from accounts.roles import role_label as get_role_label

register = template.Library()


@register.filter
def has_group(user, group_name: str) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    return user.groups.filter(name=group_name).exists()


@register.filter
def role_label(group_name: str) -> str:
    return get_role_label(group_name)

