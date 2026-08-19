from unittest.mock import Mock

from assistant_api.analytical_intents import AnalyticalIntent
from assistant_api.intent_executor import execute_analytical_intent


def test_rank_territories_uses_bounded_allowlisted_score_call():
    client = Mock()
    client.scores.return_value = [{"geographic_code": "59", "score": 80}]
    intent = AnalyticalIntent(
        intent="rank_territories",
        geographic_level="department",
        period_start="2025",
        limit=5,
    )

    result = execute_analytical_intent(intent, client)

    assert result.rows == [{"geographic_code": "59", "score": 80}]
    client.scores.assert_called_once_with(
        geographic_level="department",
        geographic_code=None,
        reference_period="2025",
        model_version=None,
        active_model_only=True,
        include_details=False,
        sort="score_desc",
        limit=5,
    )


def test_compare_periods_calculates_deterministic_change():
    client = Mock()
    client.scores.side_effect = [
        [{"reference_period": "2024", "score": 40}],
        [{"reference_period": "2025", "score": 46.5}],
    ]
    intent = AnalyticalIntent(
        intent="compare_periods",
        geographic_level="department",
        geographic_code="59",
        period_start="2024",
        period_end="2025",
    )

    result = execute_analytical_intent(intent, client)

    assert result.rows[-1]["change"] == 6.5
    assert client.scores.call_count == 2


def test_largest_increase_is_sorted_and_limited():
    client = Mock()
    client.scores.side_effect = [
        [{"geographic_code": "59", "score": 20}, {"geographic_code": "62", "score": 40}],
        [{"geographic_code": "59", "score": 35}, {"geographic_code": "62", "score": 42}],
    ]
    intent = AnalyticalIntent(
        intent="find_largest_increase",
        geographic_level="department",
        period_start="2024",
        period_end="2025",
        limit=1,
    )

    result = execute_analytical_intent(intent, client)

    assert result.rows[0]["geographic_code"] == "59"
    assert result.rows[0]["change"] == 15


def test_observability_is_reduced_to_freshness_rows():
    client = Mock()
    client.observability.return_value = {"indicator_freshness": [{"indicator_code": "score"}]}

    result = execute_analytical_intent(
        AnalyticalIntent(intent="get_data_freshness"), client
    )

    assert result.rows == [{"indicator_code": "score"}]
