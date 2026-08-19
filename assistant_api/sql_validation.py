"""AST-based validation for read-only analytical SQL."""

from __future__ import annotations

from dataclasses import dataclass

from sqlglot import exp, parse
from sqlglot.errors import ParseError


ALLOWED_VIEWS = frozenset(
    {
        "analytics_risk_scores",
        "analytics_score_factors",
        "analytics_observations",
        "analytics_model_comparisons",
        "analytics_pipeline_status",
    }
)
ALLOWED_FUNCTIONS = frozenset(
    {
        "avg",
        "coalesce",
        "count",
        "date_trunc",
        "max",
        "min",
        "round",
        "sum",
    }
)
MAX_SQL_LENGTH = 10_000
MAX_JOINS = 3
MAX_RESULT_ROWS = 200


class SQLValidationError(ValueError):
    """Stable refusal raised before any database interaction."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ValidatedSQL:
    sql: str
    tables: tuple[str, ...]
    limit: int
    join_count: int


def validate_analytical_sql(sql: str) -> ValidatedSQL:
    candidate = sql.strip()
    if not candidate or len(candidate) > MAX_SQL_LENGTH:
        raise SQLValidationError("invalid_length", "Longueur SQL invalide.")
    if "--" in candidate or "/*" in candidate or "*/" in candidate:
        raise SQLValidationError("comments_forbidden", "Commentaires SQL interdits.")
    try:
        statements = [item for item in parse(candidate, read="postgres") if item]
    except ParseError as exc:
        raise SQLValidationError("parse_error", "SQL PostgreSQL invalide.") from exc
    if len(statements) != 1:
        raise SQLValidationError("multiple_statements", "Une seule instruction est autorisée.")
    statement = statements[0]
    if not isinstance(statement, exp.Query):
        raise SQLValidationError("read_only_required", "Seule une lecture SELECT est autorisée.")
    prohibited = (
        exp.Insert,
        exp.Update,
        exp.Delete,
        exp.Create,
        exp.Drop,
        exp.Alter,
        exp.Command,
        exp.Copy,
    )
    if any(statement.find(node_type) is not None for node_type in prohibited):
        raise SQLValidationError("read_only_required", "Commande SQL interdite.")
    if statement.find(exp.Star) is not None:
        raise SQLValidationError("wildcard_forbidden", "SELECT * est interdit.")

    tables = []
    for table in statement.find_all(exp.Table):
        name = table.name.casefold()
        if table.catalog or table.db or name not in ALLOWED_VIEWS:
            raise SQLValidationError("table_forbidden", f"Vue non autorisée: {name}")
        tables.append(name)
    if not tables:
        raise SQLValidationError("table_required", "Une vue analytique est requise.")

    for function in statement.find_all(exp.Func):
        if isinstance(function, (exp.Connector, exp.Predicate)):
            continue
        name = function.sql_name().casefold()
        if name not in ALLOWED_FUNCTIONS:
            raise SQLValidationError("function_forbidden", f"Fonction non autorisée: {name}")

    join_count = sum(1 for _ in statement.find_all(exp.Join))
    if join_count > MAX_JOINS:
        raise SQLValidationError("too_many_joins", "Trop de jointures.")
    limit_node = statement.args.get("limit")
    if limit_node is None:
        raise SQLValidationError("limit_required", "LIMIT est obligatoire.")
    limit_expression = limit_node.expression
    if not isinstance(limit_expression, exp.Literal) or not limit_expression.is_int:
        raise SQLValidationError("invalid_limit", "LIMIT doit être un entier constant.")
    limit = int(limit_expression.this)
    if not 1 <= limit <= MAX_RESULT_ROWS:
        raise SQLValidationError("invalid_limit", "LIMIT dépasse la limite autorisée.")

    return ValidatedSQL(
        sql=statement.sql(dialect="postgres"),
        tables=tuple(sorted(set(tables))),
        limit=limit,
        join_count=join_count,
    )
