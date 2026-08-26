"""Generate SQL, compare parsers, validate it, then query SQLite read-only."""

from __future__ import annotations

import argparse
import importlib
import os
from pathlib import Path
import sqlite3
from time import perf_counter_ns
from typing import Callable

from sqlglot import exp, parse


DB_PATH = Path(__file__).with_name("shop.db")
FORBIDDEN = (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Alter, exp.Create, exp.Command, exp.Into)


def schema_text(path: Path) -> str:
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
        rows = connection.execute(
            "SELECT sql FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
    return "\n".join(row[0] for row in rows if row[0])


def table_names(path: Path) -> set[str]:
    """Return physical table names without reparsing SQLite DDL."""
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    return {row[0] for row in rows}


def generate_sql(question: str, schema: str) -> str:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("Installez les dépendances avec requirements.txt") from exc
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("La variable OPENAI_API_KEY est absente")
    model = os.getenv("OPENAI_MODEL", "gpt-5-mini")
    response = OpenAI().responses.create(
        model=model,
        input=(
            "Transforme la question en une unique requête SQLite en lecture seule. "
            "Utilise exclusivement le schéma fourni. Retourne uniquement le SQL, "
            "sans Markdown. Les commandes d'écriture sont interdites.\n\n"
            f"SCHÉMA:\n{schema}\n\nQUESTION:\n{question}"
        ),
    )
    return response.output_text.strip().removeprefix("```sql").removesuffix("```").strip()


def _load(module: str) -> object:
    return importlib.import_module(module)


def parser_checks(sql: str) -> list[tuple[str, str, float]]:
    adapters: list[tuple[str, Callable[[], object]]] = [
        ("SQLGlot", lambda: parse(sql, read="sqlite")),
        ("sqloxide", lambda: _load("sqloxide").parse_sql(sql, dialect="sqlite")),
        ("polyglot-sql", lambda: _load("polyglot_sql").parse(sql, dialect="sqlite")),
        ("sqlparse", lambda: _load("sqlparse").parse(sql)),
        ("SQLFluff", lambda: _load("sqlfluff").parse(sql, dialect="sqlite")),
        ("DataFusion", lambda: _load("datafusion").SessionContext().sql(sql)),
    ]
    results = []
    for name, check in adapters:
        started = perf_counter_ns()
        try:
            check()
            status = "OK"
        except (ImportError, AttributeError) as exc:
            status = f"INDISPONIBLE ({type(exc).__name__})"
        except Exception as exc:  # each parser exposes different exception classes
            status = f"ERREUR ({type(exc).__name__}: {str(exc).splitlines()[0]})"
        elapsed_ms = (perf_counter_ns() - started) / 1_000_000
        results.append((name, status, elapsed_ms))
    return results


def validate_read_only(sql: str, allowed_tables: set[str]) -> None:
    statements = parse(sql, read="sqlite")
    if len(statements) != 1:
        raise ValueError("Une seule instruction SQL est autorisée")
    tree = statements[0]
    if not isinstance(tree, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
        raise ValueError("Seules les requêtes SELECT/WITH sont autorisées")
    if any(tree.find(kind) is not None for kind in FORBIDDEN):
        raise ValueError("Instruction d'écriture interdite")
    referenced = {table.name for table in tree.find_all(exp.Table)}
    cte_names = {cte.alias_or_name for cte in tree.find_all(exp.CTE)}
    unknown = referenced - allowed_tables - cte_names
    if unknown:
        raise ValueError(f"Table(s) hors schéma : {', '.join(sorted(unknown))}")


def execute(path: Path, sql: str) -> tuple[list[str], list[tuple[object, ...]]]:
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
        cursor = connection.execute(sql)
        return [column[0] for column in cursor.description], cursor.fetchall()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question", nargs="?", help="Question en français")
    parser.add_argument("--sql", help="SQL direct, sans appel LLM")
    parser.add_argument("--db", type=Path, default=DB_PATH)
    args = parser.parse_args(argv)
    if bool(args.question) == bool(args.sql):
        parser.error("fournissez soit une question, soit --sql")
    schema = schema_text(args.db)
    sql = args.sql.strip() if args.sql else generate_sql(args.question, schema)

    print(f"\nSQL généré :\n{sql}\n")
    print("Comparaison des parseurs :")
    for name, status, elapsed_ms in parser_checks(sql):
        print(f"- {name:<13} {status:<45} {elapsed_ms:9.3f} ms")

    allowed_tables = table_names(args.db)
    validate_read_only(sql, allowed_tables)
    columns, rows = execute(args.db, sql)
    print("\nRésultat SQLite :")
    print(" | ".join(columns))
    for row in rows:
        print(" | ".join(str(value) for value in row))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
