"""Audited orchestration for advanced SQL generation and execution."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from uuid import UUID, uuid4

from sqlalchemy import Engine

from assistant_api.generation import TextGenerator
from assistant_api.repository import record_sql_execution
from assistant_api.sql_executor import (
    SQLExecutionResult,
    execute_readonly_sql,
    get_readonly_engine,
)
from assistant_api.sql_generation import (
    PROMPT_VERSION,
    SCHEMA_VERSION,
    generate_sql_candidate,
)
from assistant_api.sql_validation import SQLValidationError
from assistant_api.monitoring import metrics


@dataclass(frozen=True)
class TextToSQLResult:
    execution_id: UUID
    sql_execution: SQLExecutionResult


class SQLClarificationRequired(ValueError):
    """Raised when an advanced request needs user-provided precision."""

    code = "clarification_required"


_METRIC_TERMS = (
    "score",
    "chômage",
    "chomage",
    "pauvreté",
    "pauvrete",
    "revenu",
    "endettement",
    "dossier",
    "population",
    "emploi",
    "logement",
)
_COMPARISON_TERMS = ("compare", "comparaison", "différence", "difference")
_RANKING_TERMS = (
    "meilleur",
    "meilleure",
    "pire",
    "va mal",
    "plus élevé",
    "plus eleve",
    "plus faible",
    "classement",
)
_YEAR_PATTERN = re.compile(r"\b(?:19|20)\d{2}\b")


def require_specific_question(question: str) -> None:
    """Reject comparisons and rankings whose analytical meaning is incomplete."""
    normalized = question.casefold()
    is_comparison = any(term in normalized for term in _COMPARISON_TERMS)
    is_ranking = any(term in normalized for term in _RANKING_TERMS)
    if not (is_comparison or is_ranking):
        return
    if not any(term in normalized for term in _METRIC_TERMS):
        raise SQLClarificationRequired(
            "Précisez l'indicateur à analyser (par exemple le score, le revenu "
            "ou le nombre de dossiers), ainsi que les territoires concernés."
        )
    if not _YEAR_PATTERN.search(normalized):
        raise SQLClarificationRequired(
            "Précisez la période de comparaison ou de classement (par exemple 2024)."
        )


def run_text_to_sql(
    question: str,
    *,
    generator: TextGenerator,
    readonly_engine: Engine | None = None,
    audit_engine: Engine,
    request_id: UUID,
    actor_id: str | None,
    model_version: str,
) -> TextToSQLResult:
    execution_id = uuid4()
    sql = ""
    audit: dict[str, object] = {
        "execution_id": execution_id,
        "request_id": request_id,
        "actor_id": actor_id,
        "question": question,
        "interpretation_json": json.dumps({"method": "advanced_sql"}),
        "schema_version": SCHEMA_VERSION,
        "generated_sql": sql,
        "validation_status": "rejected",
        "validation_error": None,
        "duration_ms": None,
        "row_count": None,
        "plan_cost": None,
        "prompt_version": PROMPT_VERSION,
        "model_version": model_version,
    }
    try:
        require_specific_question(question)
        sql = generate_sql_candidate(question, generator)
        audit["generated_sql"] = sql
        execution = execute_readonly_sql(
            sql,
            engine=readonly_engine or get_readonly_engine(),
        )
    except Exception as exc:
        error_code = (
            exc.code
            if isinstance(exc, (SQLValidationError, SQLClarificationRequired))
            else type(exc).__name__
        )
        metrics.increment(
            "assistant_sql_executions_total",
            status="rejected",
            reason=error_code,
        )
        audit["validation_error"] = error_code
        record_sql_execution(audit_engine, audit)
        raise
    audit.update(
        {
            "validation_status": "accepted",
            "duration_ms": execution.duration_ms,
            "row_count": len(execution.rows),
            "plan_cost": execution.plan_cost,
        }
    )
    record_sql_execution(audit_engine, audit)
    metrics.increment("assistant_sql_executions_total", status="accepted", reason="none")
    metrics.observe("assistant_sql_execution_duration_seconds", execution.duration_ms / 1000)
    metrics.observe("assistant_sql_result_rows", len(execution.rows))
    return TextToSQLResult(execution_id=execution_id, sql_execution=execution)
