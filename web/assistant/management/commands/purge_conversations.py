"""Purge expired conversations, in dry-run mode by default."""

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from web.assistant.models import Conversation


class Command(BaseCommand):
    help = "Purge les conversations plus anciennes que la durée de rétention."

    def add_arguments(self, parser):
        parser.add_argument("--older-than-days", type=int, required=True)
        parser.add_argument("--execute", action="store_true")

    def handle(self, *args, **options):
        days = options["older_than_days"]
        if days < 1:
            raise CommandError("older-than-days doit être supérieur à zéro.")
        cutoff = timezone.now() - timedelta(days=days)
        queryset = Conversation.objects.filter(updated_at__lt=cutoff)
        count = queryset.count()
        if not options["execute"]:
            self.stdout.write(
                f"DRY_RUN conversations={count} cutoff={cutoff.isoformat()}"
            )
            return
        deleted, details = queryset.delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"PURGED conversations={count} objects={deleted} details={details}"
            )
        )
