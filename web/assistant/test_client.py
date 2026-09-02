from unittest.mock import Mock
from uuid import uuid4

from django.test import SimpleTestCase
import requests

from web.assistant.client import AssistantAPIError, AssistantClient


class AssistantClientTests(SimpleTestCase):
    def test_render_private_hostport_gets_http_scheme(self):
        client = AssistantClient("assistant-api:10000", 3, Mock())

        self.assertEqual(client.base_url, "http://assistant-api:10000")

    def test_answer_validates_and_returns_traceable_response(self):
        request_id = uuid4()
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "answer": "Réponse [S1]",
            "decision": "execute",
            "sources": [],
            "data_references": [],
            "method": "documents",
            "category": "documentary_question",
            "interpreted_filters": {},
            "result_rows": [],
            "generated_sql": None,
            "sql_execution_id": None,
            "request_id": str(request_id),
        }
        session = Mock()
        session.post.return_value = response
        client = AssistantClient("http://assistant.test", 3, session)

        result = client.answer("Définissez l’inflation")

        self.assertEqual(result["request_id"], str(request_id))
        self.assertEqual(session.post.call_args.kwargs["timeout"], 3)

    def test_sql_mode_sends_internal_token(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "answer": "Résultat [D1]", "decision": "execute",
            "sources": [], "data_references": [],
            "method": "advanced_sql", "category": "advanced_sql",
            "interpreted_filters": {}, "result_rows": [{"score": 42}],
            "generated_sql": "SELECT score FROM analytics_risk_scores LIMIT 1",
            "sql_execution_id": str(uuid4()), "request_id": str(uuid4()),
        }
        session = Mock()
        session.post.return_value = response
        client = AssistantClient("http://assistant.test", 3, session)

        with self.settings(ASSISTANT_INTERNAL_TOKEN="internal-test-token"):
            client.answer("Score médian", mode="sql", actor_id="7")

        call = session.post.call_args
        self.assertEqual(call.kwargs["headers"]["X-Internal-Token"], "internal-test-token")
        self.assertEqual(call.kwargs["json"]["actor_id"], "7")

    def test_timeout_is_a_stable_ui_error(self):
        session = Mock()
        session.post.side_effect = requests.Timeout()
        client = AssistantClient("http://assistant.test", 1, session)

        with self.assertRaisesMessage(AssistantAPIError, "trop de temps"):
            client.answer("Question métier")

    def test_information_mode_sends_internal_token(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "answer": "Réponse", "decision": "execute", "sources": [],
            "data_references": [], "method": "documents",
            "category": "documentary_question", "interpreted_filters": {},
            "result_rows": [], "generated_sql": None,
            "sql_execution_id": None, "request_id": str(uuid4()),
        }
        session = Mock()
        session.post.return_value = response

        with self.settings(ASSISTANT_INTERNAL_TOKEN="internal-test-token"):
            AssistantClient("http://assistant.test", 3, session).answer("Question")

        self.assertEqual(
            session.post.call_args.kwargs["headers"]["X-Internal-Token"],
            "internal-test-token",
        )

    def test_invalid_response_is_rejected(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"answer": "sans provenance"}
        session = Mock()
        session.post.return_value = response
        client = AssistantClient("http://assistant.test", 1, session)

        with self.assertRaisesMessage(AssistantAPIError, "invalide"):
            client.answer("Question métier")

    def test_authentication_error_has_safe_ui_message(self):
        response = Mock()
        response.raise_for_status.side_effect = requests.HTTPError(response=response)
        response.status_code = 401
        session = Mock()
        session.post.return_value = response

        with self.assertRaisesMessage(AssistantAPIError, "n’est pas autorisé"):
            AssistantClient("http://assistant.test", 1, session).answer("Question")

    def test_server_error_has_safe_ui_message(self):
        response = Mock()
        response.raise_for_status.side_effect = requests.HTTPError(response=response)
        response.status_code = 503
        session = Mock()
        session.post.return_value = response

        with self.assertRaisesMessage(AssistantAPIError, "temporairement indisponible"):
            AssistantClient("http://assistant.test", 1, session).answer("Question")
