"""Read-only PostgreSQL execution boundary for validated analytical SQL."""

from __future__ import annotations

from dataclasses import dataclass
import os
from time import monotonic

from sqlalchemy import Engine, create_engine, text

from assistant_api.sql_validation import ValidatedSQL, validate_analytical_sql


MAX_PLAN_COST = 100_000
MAX_PLAN_ROWS = 1_000_000
STATEMENT_TIMEOUT_MS = 5_000


class ReadonlyDatabaseConfigurationError(RuntimeError):
    """Raised when the dedicated read-only connection is missing."""


class SQLCostError(RuntimeError):
    """Raised when PostgreSQL estimates an excessive query cost."""


@dataclass(frozen=True)
class SQLExecutionResult:
    validated: ValidatedSQL
    rows: list[dict]
    duration_ms: int
    plan_cost: float
    plan_rows: int


def get_readonly_engine() -> Engine:
    url = os.getenv("ANALYTICS_READONLY_DATABASE_URL", "").strip()
    if not url.startswith("postgresql+psycopg://"):
        raise ReadonlyDatabaseConfigurationError(
            "ANALYTICS_READONLY_DATABASE_URL doit utiliser postgresql+psycopg."
        )
    return create_engine(url, future=True, pool_pre_ping=True)


def execute_readonly_sql(
    sql: str,
    *,
    engine: Engine | None = None,
) -> SQLExecutionResult:
    validated = validate_analytical_sql(sql)
    database = engine or get_readonly_engine()
    started = monotonic()
    with database.connect() as connection:
        transaction = connection.begin()
        try:
            connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            connection.exec_driver_sql(
                f"SET LOCAL statement_timeout = '{STATEMENT_TIMEOUT_MS}ms'"
            )
            plan_payload = connection.execute(
                text(f"EXPLAIN (FORMAT JSON) {validated.sql}")
            ).scalar_one()
            plan = _extract_plan(plan_payload)
            plan_cost = float(plan.get("Total Cost", 0))
            plan_rows = int(plan.get("Plan Rows", 0))
            if plan_cost > MAX_PLAN_COST or plan_rows > MAX_PLAN_ROWS:
                raise SQLCostError("La requête dépasse le coût analytique autorisé.")
            rows = [
                dict(row)
                for row in connection.execute(text(validated.sql)).mappings().all()
            ]
        finally:
            transaction.rollback()
    return SQLExecutionResult(
        validated=validated,
        rows=rows,
        duration_ms=round((monotonic() - started) * 1000),
        plan_cost=plan_cost,
        plan_rows=plan_rows,
    )


def _extract_plan(payload: object) -> dict:
    if isinstance(payload, str):
        import json

        payload = json.loads(payload)
    if not isinstance(payload, list) or not payload:
        raise SQLCostError("Le plan PostgreSQL est invalide.")
    root = payload[0]
    if not isinstance(root, dict) or not isinstance(root.get("Plan"), dict):
        raise SQLCostError("Le plan PostgreSQL est invalide.")
    return root["Plan"]
