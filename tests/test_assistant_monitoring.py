import os

import pytest

from assistant_api.monitoring import AssistantMetrics, render_evaluation_metrics


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


def test_evaluation_metrics_are_rendered_from_report(tmp_path):
    report = tmp_path / "evaluation.json"
    report.write_text(
        '{"status":"PASS","metrics":{"availability":1.0,'
        '"case_pass_rate":0.75,"passed_cases":3,"total_cases":4}}',
        encoding="utf-8",
    )
    os.utime(report, (1_700_000_000, 1_700_000_000))

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr("assistant_api.monitoring.time", lambda: 1_700_000_060)
        rendered = render_evaluation_metrics(report)

    assert "assistant_evaluation_report_available 1" in rendered
    assert "assistant_evaluation_report_timestamp_seconds 1.7e+09" in rendered
    assert "assistant_evaluation_report_age_seconds 60" in rendered
    assert 'assistant_evaluation_score{metric="availability"} 1' in rendered
    assert 'assistant_evaluation_score{metric="case_pass_rate"} 0.75' in rendered
    assert 'assistant_evaluation_cases{result="passed"} 3' in rendered
    assert 'assistant_evaluation_status{status="pass"} 1' in rendered


def test_missing_evaluation_report_is_reported_without_breaking_scrape(tmp_path):
    rendered = render_evaluation_metrics(tmp_path / "missing.json")

    assert rendered == "assistant_evaluation_report_available 0\n"
