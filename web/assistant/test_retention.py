from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from web.assistant.models import Conversation


class ConversationRetentionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("retention-user")
        self.old = Conversation.objects.create(user=self.user, title="Ancienne")
        Conversation.objects.filter(pk=self.old.pk).update(
            updated_at=timezone.now() - timedelta(days=100)
        )
        self.recent = Conversation.objects.create(user=self.user, title="Récente")

    def test_command_is_dry_run_by_default(self):
        output = StringIO()
        call_command("purge_conversations", older_than_days=90, stdout=output)
        self.assertTrue(Conversation.objects.filter(pk=self.old.pk).exists())
        self.assertIn("DRY_RUN conversations=1", output.getvalue())

    def test_execute_deletes_only_expired_conversations(self):
        call_command("purge_conversations", older_than_days=90, execute=True)
        self.assertFalse(Conversation.objects.filter(pk=self.old.pk).exists())
        self.assertTrue(Conversation.objects.filter(pk=self.recent.pk).exists())
