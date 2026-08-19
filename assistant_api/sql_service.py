"""Audited orchestration for advanced SQL generation and execution."""

from __future__ import annotations

from dataclasses import dataclass
import json
from uuid import UUID, uuid4

from sqlalchemy import Engine

from assistant_api.generation import TextGenerator
from assistant_api.repository import record_sql_execution
from assistant_api.sql_executor import SQLExecutionResult, execute_readonly_sql
from assistant_api.sql_generation import (
    PROMPT_VERSION,
    SCHEMA_VERSION,
    generate_sql_candidate,
)
from assistant_api.sql_validation import SQLValidationError


@dataclass(frozen=True)
class TextToSQLResult:
    execution_id: UUID
    sql_execution: SQLExecutionResult


def run_text_to_sql(
    question: str,
    *,
    generator: TextGenerator,
    readonly_engine: Engine,
    audit_engine: Engine,
    request_id: UUID,
    actor_id: str | None,
    model_version: str,
) -> TextToSQLResult:
    execution_id = uuid4()
    sql = ""
    audit = {
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
        sql = generate_sql_candidate(question, generator)
        audit["generated_sql"] = sql
        execution = execute_readonly_sql(sql, engine=readonly_engine)
    except Exception as exc:
        audit["validation_error"] = (
            exc.code if isinstance(exc, SQLValidationError) else type(exc).__name__
        )
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
    return TextToSQLResult(execution_id=execution_id, sql_execution=execution)
