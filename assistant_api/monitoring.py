"""Metrics dedicated to RAG and read-only SQL operations."""

from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path
from threading import Lock
from time import time


EVALUATION_METRICS = (
    "availability",
    "case_pass_rate",
    "category_accuracy",
    "method_accuracy",
    "refusal_recall",
    "evidence_compliance",
    "publisher_compliance",
    "required_publisher_compliance",
)
DEFAULT_EVALUATION_REPORT = Path("app/reports/rag/rag_evaluation.json")


def render_evaluation_metrics(report_path: str | Path | None = None) -> str:
    """Render low-cardinality gauges from the latest versioned RAG evaluation."""
    path = Path(
        report_path
        or os.getenv("ASSISTANT_EVALUATION_REPORT", str(DEFAULT_EVALUATION_REPORT))
    )
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
        raw_metrics = report["metrics"]
        report_timestamp = path.stat().st_mtime
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return "assistant_evaluation_report_available 0\n"

    lines = [
        "assistant_evaluation_report_available 1",
        f"assistant_evaluation_report_timestamp_seconds {report_timestamp:g}",
        f"assistant_evaluation_report_age_seconds {max(0.0, time() - report_timestamp):g}",
    ]
    for name in EVALUATION_METRICS:
        value = raw_metrics.get(name)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            lines.append(f'assistant_evaluation_score{{metric="{name}"}} {value:g}')

    for result, key in (("passed", "passed_cases"), ("total", "total_cases")):
        value = raw_metrics.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            lines.append(f'assistant_evaluation_cases{{result="{result}"}} {value}')

    status = str(report.get("status", "unknown")).strip().lower()
    if status not in {"pass", "fail"}:
        status = "unknown"
    lines.append(f'assistant_evaluation_status{{status="{status}"}} 1')
    return "\n".join(lines) + "\n"


class AssistantMetrics:
    def __init__(self) -> None:
        self._values: defaultdict[
            tuple[str, tuple[tuple[str, str], ...]], float
        ] = defaultdict(float)
        self._lock = Lock()

    def increment(self, name: str, **labels: str) -> None:
        key = (name, tuple(sorted((key, str(value)) for key, value in labels.items())))
        with self._lock:
            self._values[key] += 1

    def observe(self, name: str, value: float, **labels: str) -> None:
        with self._lock:
            label_values = tuple(sorted((key, str(val)) for key, val in labels.items()))
            self._values[(name + "_count", label_values)] += 1
            self._values[(name + "_sum", label_values)] += value

    def render(self) -> str:
        with self._lock:
            values = sorted(self._values.items())
        lines = []
        for (name, labels), value in values:
            suffix = ""
            if labels:
                suffix = "{" + ",".join(
                    f'{key}="{val.replace(chr(34), chr(92) + chr(34))}"'
                    for key, val in labels
                ) + "}"
            lines.append(f"{name}{suffix} {value:g}")
        return "\n".join(lines) + "\n"

    def total(self, name: str, **labels: str) -> float:
        """Return an aggregate without exposing the mutable metrics store."""
        expected = {key: str(value) for key, value in labels.items()}
        with self._lock:
            return sum(
                value
                for (metric_name, metric_labels), value in self._values.items()
                if metric_name == name
                and expected.items() <= dict(metric_labels).items()
            )

    def summary(self) -> dict[str, object]:
        decisions = {
            decision: int(self.total("assistant_decisions_total", decision=decision))
            for decision in ("execute", "clarify", "refuse")
        }
        duration_count = self.total("assistant_http_request_duration_seconds_count")
        duration_sum = self.total("assistant_http_request_duration_seconds_sum")
        return {
            "decisions": decisions,
            "provider_errors": int(self.total("assistant_provider_errors_total")),
            "sql_validation_errors": int(
                self.total("assistant_sql_executions_total", status="rejected")
            ),
            "average_http_latency_seconds": (
                duration_sum / duration_count if duration_count else 0.0
            ),
            "persistence": "process_memory",
        }


metrics = AssistantMetrics()
