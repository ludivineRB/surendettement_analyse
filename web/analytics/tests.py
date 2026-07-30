from unittest.mock import Mock

import requests
from django.test import SimpleTestCase

from web.analytics.client import AnalyticsAPIError, AnalyticsClient


SCORE = {
    "geographic_level": "department",
    "geographic_code": "59",
    "geographic_name": "Nord",
    "reference_period": "2025",
    "score": 42.5,
    "coverage_ratio": 0.9,
    "status": "valid",
    "model": {"code": "default", "version": "1.2.0"},
    "details": [],
}


class AnalyticsClientTests(SimpleTestCase):
    def client_with_response(self, payload):
        response = Mock()
        response.json.return_value = payload
        response.raise_for_status.return_value = None
        session = Mock()
        session.get.return_value = response
        return AnalyticsClient(
            base_url="http://api.test",
            timeout=2,
            session=session,
        ), session

    def test_list_scores_validates_response_and_passes_filters(self):
        client, session = self.client_with_response([SCORE])
        result = client.list_scores(
            geographic_level="department",
            geographic_code="59",
        )
        self.assertEqual(result[0]["score"], 42.5)
        self.assertEqual(
            session.get.call_args.kwargs["params"]["geographic_code"],
            "59",
        )
        self.assertEqual(session.get.call_args.kwargs["timeout"], 2)

    def test_series_escapes_path_and_validates_nested_scores(self):
        client, session = self.client_with_response(
            {
                "geographic_level": "department",
                "geographic_code": "2A",
                "count": 1,
                "series": [SCORE],
            }
        )
        result = client.get_series("department", "2A")
        self.assertEqual(result["count"], 1)
        self.assertIn("/department/2A", session.get.call_args.args[0])

    def test_timeout_is_exposed_as_stable_application_error(self):
        session = Mock()
        session.get.side_effect = requests.Timeout()
        client = AnalyticsClient(
            base_url="http://api.test",
            timeout=1,
            session=session,
        )
        with self.assertRaisesMessage(
            AnalyticsAPIError,
            "ne répond pas",
        ):
            client.list_models()

    def test_http_error_is_exposed_as_stable_application_error(self):
        response = Mock(status_code=503)
        error = requests.HTTPError(response=response)
        response.raise_for_status.side_effect = error
        session = Mock()
        session.get.return_value = response
        client = AnalyticsClient(
            base_url="http://api.test",
            timeout=1,
            session=session,
        )
        with self.assertRaisesMessage(
            AnalyticsAPIError,
            "temporairement indisponible",
        ):
            client.get_observability()

    def test_invalid_payload_is_rejected(self):
        client, _ = self.client_with_response([{"score": 10}])
        with self.assertRaisesMessage(
            AnalyticsAPIError,
            "réponse du service analytique est invalide",
        ):
            client.list_scores()

    def test_invalid_json_is_rejected(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.side_effect = ValueError("invalid JSON")
        session = Mock()
        session.get.return_value = response
        client = AnalyticsClient(
            base_url="http://api.test",
            timeout=1,
            session=session,
        )
        with self.assertRaisesMessage(
            AnalyticsAPIError,
            "réponse du service analytique est invalide",
        ):
            client.list_models()

    def test_insufficient_model_comparison_is_valid(self):
        client, _ = self.client_with_response(
            {
                "status": "insufficient_data",
                "version_a": "1.1.0",
                "version_b": "1.2.0",
                "rows": [],
            }
        )
        result = client.compare_models(version_a="1.1.0", version_b="1.2.0")
        self.assertEqual(result["status"], "insufficient_data")
