"""SQLite helpers for the analytical macro/surendettement database."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from app.core.config import settings


@contextmanager
def analytics_connection(db_path: str | None = None) -> Iterator[sqlite3.Connection]:
    path = Path(db_path or settings.ANALYTICS_DB_PATH)
    if not path.exists():
        raise FileNotFoundError(f"Analytics database not found: {path}")
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        ensure_override_table(connection)
        yield connection
        connection.commit()
    finally:
        connection.close()


def ensure_override_table(connection: sqlite3.Connection) -> None:
    conformed = all(
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        for table in ("dim_period", "dim_department", "dim_indicator")
    )
    if not conformed:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS fact_macro_override (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reference_year INTEGER NOT NULL,
                departement_code TEXT NOT NULL,
                indicator_code TEXT NOT NULL,
                indicator_name TEXT,
                indicator_group TEXT,
                value REAL NOT NULL,
                source_note TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_macro_override_lookup
            ON fact_macro_override(
                reference_year, departement_code, indicator_code
            )
            """
        )
        return
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS fact_macro_override (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            period_key TEXT NOT NULL,
            reference_year INTEGER NOT NULL,
            departement_code TEXT NOT NULL,
            indicator_key TEXT NOT NULL,
            indicator_code TEXT NOT NULL,
            indicator_name TEXT,
            indicator_group TEXT,
            value REAL NOT NULL,
            source_note TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(period_key) REFERENCES dim_period(period_key),
            FOREIGN KEY(departement_code)
                REFERENCES dim_department(departement_code),
            FOREIGN KEY(indicator_key) REFERENCES dim_indicator(indicator_key)
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_macro_override_lookup
        ON fact_macro_override(period_key, departement_code, indicator_key)
        """
    )


def fetch_all(connection: sqlite3.Connection, query: str, params: dict[str, Any] | None = None) -> list[dict]:
    rows = connection.execute(query, params or {}).fetchall()
    return [dict(row) for row in rows]


def fetch_one(connection: sqlite3.Connection, query: str, params: dict[str, Any] | None = None) -> dict | None:
    row = connection.execute(query, params or {}).fetchone()
    return dict(row) if row else None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
