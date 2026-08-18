from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from web.assistant.models import Conversation, ConversationMessage


class AssistantViewTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user("alice", password="test-pass")
        self.other = user_model.objects.create_user("bob", password="test-pass")

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("assistant"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_user_cannot_read_another_users_conversation(self):
        conversation = Conversation.objects.create(
            user=self.other,
            title="Conversation privée",
        )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("assistant-conversation", args=(conversation.id,))
        )

        self.assertEqual(response.status_code, 404)

    @patch("web.assistant.views.AssistantClient.answer")
    def test_successful_answer_is_persisted_with_provenance(self, answer):
        answer.return_value = {
            "answer": "L’inflation est mesurée par l’IPC. [S1]",
            "sources": [
                {
                    "title": "Définition IPC",
                    "url": "https://www.insee.fr/fr/test",
                    "publisher": "Insee",
                    "reference_period": "2026",
                }
            ],
            "data_references": [],
            "method": "documents",
            "request_id": str(uuid4()),
        }
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("assistant"),
            {"question": "Qu’est-ce que l’inflation ?"},
        )

        conversation = Conversation.objects.get(user=self.user)
        self.assertRedirects(
            response,
            reverse("assistant-conversation", args=(conversation.id,)),
        )
        messages = list(conversation.messages.all())
        self.assertEqual(
            [message.role for message in messages],
            [
                ConversationMessage.Role.USER,
                ConversationMessage.Role.ASSISTANT,
            ],
        )
        self.assertEqual(messages[1].method, "documents")
        self.assertEqual(messages[1].citations[0]["publisher"], "Insee")
