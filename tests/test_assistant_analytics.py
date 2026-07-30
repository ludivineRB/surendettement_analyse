from unittest.mock import Mock, patch

import pytest
import requests

from assistant_api.analytics import AnalyticsClient, AnalyticsUnavailable


@patch("assistant_api.analytics.requests.get")
def test_fetch_uses_allowlisted_path_and_bounded_limit(mock_get):
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
