"""Delete a local user and anonymize retained security audit records."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction


class Command(BaseCommand):
    help = "Supprime un compte et ses données applicatives (simulation par défaut)."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("--execute", action="store_true")

    def handle(self, *args, **options):
        try:
            user = get_user_model().objects.get(username=options["username"])
        except get_user_model().DoesNotExist as exc:
            raise CommandError("Utilisateur introuvable.") from exc
        conversations = user.assistant_conversations.count()
        if not options["execute"]:
            self.stdout.write(
                f"DRY_RUN user={user.username} conversations={conversations}"
            )
            return
        actor_id = str(user.pk)
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SELECT to_regclass('assistant.sql_executions')")
                if cursor.fetchone()[0] is not None:
                    cursor.execute(
                        "UPDATE assistant.sql_executions "
                        "SET actor_id = NULL WHERE actor_id = %s",
                        [actor_id],
                    )
            user.delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"DELETED user={options['username']} conversations={conversations}"
            )
        )
