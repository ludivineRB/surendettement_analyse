"""Database boundary for the Assistant API."""

from __future__ import annotations

import os

from sqlalchemy import Engine, create_engine


class AssistantDatabaseConfigurationError(RuntimeError):
    """Raised when the service database is not explicitly configured."""


def get_database_url() -> str:
    database_url = os.getenv("ASSISTANT_DATABASE_URL", "").strip()
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace(
            "postgresql://", "postgresql+psycopg://", 1
        )
    if not database_url.startswith("postgresql+psycopg://"):
        raise AssistantDatabaseConfigurationError(
            "ASSISTANT_DATABASE_URL must use postgresql+psycopg"
        )
    return database_url


def get_engine(database_url: str | None = None) -> Engine:
    return create_engine(
        database_url or get_database_url(),
        future=True,
        pool_pre_ping=True,
    )
