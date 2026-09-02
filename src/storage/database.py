"""Database connection and persistence helpers."""

from __future__ import annotations

import os
from typing import Iterable

import pandas as pd
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from src.storage.models import Base, SurendettementData


def get_database_url() -> str:
    """Return DB URL, SQLite by default, overridable for PostgreSQL."""
    return os.getenv("DATABASE_URL", "sqlite:///data/processed/surendettement.db")


def get_engine():
    return create_engine(get_database_url(), future=True)


def init_db() -> None:
    engine = get_engine()
    Base.metadata.create_all(engine)


def get_session_factory():
    return sessionmaker(bind=get_engine(), class_=Session, expire_on_commit=False)


def save_dataframe(df: pd.DataFrame) -> int:
    """Persist dataframe rows to surendettement_data table."""
    factory = get_session_factory()
    inserted = 0
    with factory() as session:
        records: Iterable[SurendettementData] = (
            SurendettementData(
                year=_safe_int(row.get("year")),
                region=row.get("departement") or row.get("region"),
                indicator=row.get("indicator_name") or row.get("indicator") or "unknown",
                value=_safe_float(row.get("value")),
                source_file=row.get("source_file") or "unknown",
            )
            for row in df.to_dict(orient="records")
        )
        batch = list(records)
        session.add_all(batch)
        session.commit()
        inserted = len(batch)
    return inserted


def get_existing_source_files() -> set[str]:
    """Return already ingested source_file names."""
    engine = get_engine()
    inspector = inspect(engine)
    if not inspector.has_table("surendettement_data"):
        return set()

    with engine.connect() as connection:
        rows = connection.execute(text("SELECT DISTINCT source_file FROM surendettement_data"))
        return {row[0] for row in rows if row[0]}


def _safe_int(value):
    try:
        if pd.isna(value):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_float(value):
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
