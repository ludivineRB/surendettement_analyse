from unittest.mock import Mock, patch

import pytest
import requests

from assistant_api.analytics import AnalyticsClient, AnalyticsUnavailable


@patch("assistant_api.analytics.requests.get")
def test_fetch_uses_allowlisted_path_and_bounded_limit(mock_get, monkeypatch):
    monkeypatch.delenv("ASSISTANT_INTERNAL_TOKEN", raising=False)
    response = Mock()
    response.json.return_value = [{"indicator_code": "NB_DOSSIERS"}]
    response.raise_for_status.return_value = None
    mock_get.return_value = response

    result = AnalyticsClient("http://analytics.test").fetch(
        "surendettement",
        filters={"reference_year": 2024},
        limit=50_000,
    )

    assert result == [{"indicator_code": "NB_DOSSIERS"}]
    mock_get.assert_called_once_with(
        "http://analytics.test/api/data/surendettement",
        params={"reference_year": 2024, "limit": 500},
        timeout=5,
    )


@patch("assistant_api.analytics.requests.get")
def test_fetch_hides_transport_details(mock_get):
    mock_get.side_effect = requests.ConnectionError("internal hostname")

    with pytest.raises(AnalyticsUnavailable) as error:
        AnalyticsClient("http://analytics.test").fetch("indicators")

    assert "internal hostname" not in str(error.value)


@patch("assistant_api.analytics.requests.get")
def test_fetch_forwards_configured_internal_token(mock_get, monkeypatch):
    monkeypatch.setenv("ASSISTANT_INTERNAL_TOKEN", "internal-test-token")
    response = Mock()
    response.json.return_value = []
    response.raise_for_status.return_value = None
    mock_get.return_value = response

    AnalyticsClient("http://analytics.test").fetch("indicators")

    assert mock_get.call_args.kwargs["headers"] == {
        "X-Internal-Token": "internal-test-token"
    }


def test_render_private_hostport_gets_http_scheme():
    client = AnalyticsClient(base_url="analytics-api:10000")

    assert client.base_url == "http://analytics-api:10000"


def test_render_timeout_can_cover_free_tier_cold_start(monkeypatch):
    monkeypatch.setenv("ANALYTICS_API_TIMEOUT_SECONDS", "90")

    assert AnalyticsClient("https://analytics.test").timeout_seconds == 90
