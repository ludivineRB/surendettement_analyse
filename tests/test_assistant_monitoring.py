import pytest

from assistant_api.monitoring import AssistantMetrics


def test_summary_calculates_decisions_errors_and_average_latency():
    metrics = AssistantMetrics()
    metrics.increment("assistant_decisions_total", decision="execute")
    metrics.increment("assistant_decisions_total", decision="clarify")
    metrics.increment("assistant_provider_errors_total", provider="openai")
    metrics.increment("assistant_sql_executions_total", status="rejected")
    metrics.observe("assistant_http_request_duration_seconds", 0.2)
    metrics.observe("assistant_http_request_duration_seconds", 0.4)

    summary = metrics.summary()

    assert summary["decisions"] == {"execute": 1, "clarify": 1, "refuse": 0}
    assert summary["provider_errors"] == 1
    assert summary["sql_validation_errors"] == 1
    assert summary["average_http_latency_seconds"] == pytest.approx(0.3)
    assert summary["persistence"] == "process_memory"
