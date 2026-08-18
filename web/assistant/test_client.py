from unittest.mock import Mock
from uuid import uuid4

from django.test import SimpleTestCase
import requests

from web.assistant.client import AssistantAPIError, AssistantClient


class AssistantClientTests(SimpleTestCase):
    def test_answer_validates_and_returns_traceable_response(self):
        request_id = uuid4()
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "answer": "Réponse [S1]",
            "sources": [],
            "data_references": [],
            "method": "documents",
            "request_id": str(request_id),
        }
        session = Mock()
        session.post.return_value = response
        client = AssistantClient("http://assistant.test", 3, session)

        result = client.answer("Définissez l’inflation")

        self.assertEqual(result["request_id"], str(request_id))
        self.assertEqual(session.post.call_args.kwargs["timeout"], 3)

    def test_timeout_is_a_stable_ui_error(self):
        session = Mock()
        session.post.side_effect = requests.Timeout()
        client = AssistantClient("http://assistant.test", 1, session)

        with self.assertRaisesMessage(AssistantAPIError, "trop de temps"):
            client.answer("Question métier")

    def test_invalid_response_is_rejected(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"answer": "sans provenance"}
        session = Mock()
        session.post.return_value = response
        client = AssistantClient("http://assistant.test", 1, session)

        with self.assertRaisesMessage(AssistantAPIError, "invalide"):
            client.answer("Question métier")
