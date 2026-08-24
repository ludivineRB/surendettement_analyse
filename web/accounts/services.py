"""Role assignment helpers."""

from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import connection, transaction

ROLE_NAMES = ("viewer", "analyst", "administrator")


def assign_role(user, role_name: str) -> None:
    if role_name not in ROLE_NAMES:
        raise ValidationError(f"Unknown role: {role_name}")
    role = Group.objects.get(name=role_name)
    user.groups.remove(*Group.objects.filter(name__in=ROLE_NAMES))
    user.groups.add(role)


def delete_account_data(user) -> int:
    """Delete an account and its conversations, anonymizing retained SQL audits."""
    conversation_count = user.assistant_conversations.count()
    actor_id = str(user.pk)
    with transaction.atomic():
        table_names = connection.introspection.table_names()
        if "sql_executions" in table_names:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE sql_executions SET actor_id = NULL WHERE actor_id = %s",
                    [actor_id],
                )
        elif connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SELECT to_regclass('assistant.sql_executions')")
                if cursor.fetchone()[0] is not None:
                    cursor.execute(
                        "UPDATE assistant.sql_executions "
                        "SET actor_id = NULL WHERE actor_id = %s",
                        [actor_id],
                    )
        user.delete()
    return conversation_count
