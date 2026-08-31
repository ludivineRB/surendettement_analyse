"""SQLGlot security boundary for the autonomous SQLite benchmark."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
import sqlite3
from typing import Any


MAX_JOINS = 3
MAX_LIMIT = 200
FORBIDDEN_FUNCTIONS = {"load_extension", "readfile", "writefile", "sleep", "pg_sleep"}


@dataclass(frozen=True)
class ValidationResult:
    accepted: bool
    parser: str
    reason_code: str
    reason: str
    tables: list[str]
    columns: list[str]
    join_count: int
    limit: int | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def schema_from_sqlite(path: Path) -> dict[str, set[str]]:
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        return {
            table: {row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')}
            for (table,) in tables
        }


def validate_sql(sql: str, schema: dict[str, set[str]]) -> ValidationResult:
    try:
        from sqlglot import exp, parse
    except ImportError as exc:  # pragma: no cover - installation error
        raise RuntimeError("sqlglot is required") from exc

    def rejected(code: str, reason: str, *, tables: set[str] | None = None,
                 columns: set[str] | None = None, joins: int = 0,
                 limit: int | None = None) -> ValidationResult:
        return ValidationResult(False, "sqlglot", code, reason, sorted(tables or set()),
                                sorted(columns or set()), joins, limit)

    if not isinstance(sql, str) or not sql.strip():
        return rejected("empty_sql", "SQL vide")
    if re.search(r"--|/\*|\*/", sql):
        return rejected("comment_forbidden", "Les commentaires SQL sont interdits")
    try:
        statements = parse(sql, read="sqlite")
    except Exception as exc:
        return rejected("invalid_sql", f"SQL invalide: {type(exc).__name__}")
    if len(statements) != 1:
        return rejected("multiple_statements", "Une seule instruction est autorisée")
    tree = statements[0]
    forbidden = (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Alter, exp.Create,
                 exp.Command, exp.Into, exp.Merge, exp.Transaction)
    if not isinstance(tree, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
        return rejected("read_only_required", "Seules les requêtes SELECT/WITH sont autorisées")
    if any(tree.find(kind) is not None for kind in forbidden):
        return rejected("read_only_required", "Une opération d'écriture ou DDL a été détectée")
    if tree.find(exp.Star) is not None:
        return rejected("wildcard_forbidden", "SELECT * est interdit")

    ctes = {cte.alias_or_name for cte in tree.find_all(exp.CTE)}
    physical_tables = {table.name for table in tree.find_all(exp.Table) if table.name not in ctes}
    unknown_tables = physical_tables - schema.keys()
    joins = sum(1 for _ in tree.find_all(exp.Join))
    if unknown_tables:
        return rejected("table_forbidden", f"Tables non autorisées: {sorted(unknown_tables)}",
                        tables=physical_tables, joins=joins)
    if joins > MAX_JOINS:
        return rejected("too_many_joins", f"Maximum {MAX_JOINS} jointures",
                        tables=physical_tables, joins=joins)

    aliases = {table.alias_or_name: table.name for table in tree.find_all(exp.Table)}
    all_columns = set().union(*(schema[t] for t in physical_tables)) if physical_tables else set()
    used_columns: set[str] = set()
    for column in tree.find_all(exp.Column):
        used_columns.add(column.name)
        table_name = aliases.get(column.table, column.table) if column.table else None
        if table_name in ctes:
            continue
        allowed = schema.get(table_name, all_columns) if table_name else all_columns
        if column.name not in allowed:
            return rejected("column_forbidden", f"Colonne inconnue: {column.sql()}",
                            tables=physical_tables, columns=used_columns, joins=joins)
    for function in tree.find_all(exp.Func):
        function_name = getattr(function, "name", "") or function.sql_name()
        if function_name.lower() in FORBIDDEN_FUNCTIONS:
            return rejected("function_forbidden", f"Fonction interdite: {function_name}",
                            tables=physical_tables, columns=used_columns, joins=joins)

    limit_node = tree.args.get("limit")
    limit: int | None = None
    if limit_node is not None:
        try:
            limit = int(limit_node.expression.name)
        except (AttributeError, TypeError, ValueError):
            return rejected("invalid_limit", "LIMIT doit être un entier constant",
                            tables=physical_tables, columns=used_columns, joins=joins)
        if limit < 1 or limit > MAX_LIMIT:
            return rejected("invalid_limit", f"LIMIT doit être compris entre 1 et {MAX_LIMIT}",
                            tables=physical_tables, columns=used_columns, joins=joins, limit=limit)
    aggregate = any(tree.find(kind) is not None for kind in (exp.AggFunc, exp.Group))
    if physical_tables and not aggregate and limit is None:
        return rejected("limit_required", "LIMIT est obligatoire pour les lignes détaillées",
                        tables=physical_tables, columns=used_columns, joins=joins)
    return ValidationResult(True, "sqlglot", "accepted", "Requête autorisée",
                            sorted(physical_tables), sorted(used_columns), joins, limit)
