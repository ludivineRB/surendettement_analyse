from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from web.assistant.models import Conversation


class DeleteUserDataTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("privacy-user")
        Conversation.objects.create(user=self.user, title="Privée")

    def test_dry_run_preserves_user(self):
        output = StringIO()
        call_command("delete_user_data", "privacy-user", stdout=output)
        self.assertTrue(
            get_user_model().objects.filter(username="privacy-user").exists()
        )
        self.assertIn("DRY_RUN", output.getvalue())

    def test_execute_deletes_user_and_conversations(self):
        call_command("delete_user_data", "privacy-user", execute=True)
        self.assertFalse(
            get_user_model().objects.filter(username="privacy-user").exists()
        )
        self.assertFalse(Conversation.objects.exists())
