"""Role assignment helpers."""

from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError

ROLE_NAMES = ("viewer", "analyst", "administrator")


def assign_role(user, role_name: str) -> None:
    if role_name not in ROLE_NAMES:
        raise ValidationError(f"Unknown role: {role_name}")
    role = Group.objects.get(name=role_name)
    user.groups.remove(*Group.objects.filter(name__in=ROLE_NAMES))
    user.groups.add(role)
