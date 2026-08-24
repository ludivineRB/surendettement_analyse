"""Versioned operational thresholds for LOT-16."""

THRESHOLDS_VERSION = "1.0.0"

THRESHOLDS = {
    "database_latency_warning_ms": 250,
    "database_latency_critical_ms": 1000,
    "pipeline_running_warning_minutes": 120,
    "pipeline_stale_warning_hours": 26,
    "http_error_rate_warning": 0.02,
    "http_latency_p95_warning_seconds": 1.0,
    "rag_empty_result_warning_rate": 0.20,
    "rag_evaluation_minimum_pass_rate": 0.90,
    "sql_rejection_warning_rate": 0.25,
}
