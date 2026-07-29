"""Small versioned migration registry compatible with SQLite and PostgreSQL."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy import Engine, text

from src.storage.database import get_engine
from src.storage.models import Base


@dataclass(slots=True)
class MigrationReport:
    applied: list[str]
    already_applied: list[str]


def apply_migrations(engine: Engine | None = None) -> MigrationReport:
    engine = engine or get_engine()
    applied, already_applied = [], []
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version VARCHAR(64) PRIMARY KEY,
                    description VARCHAR(512) NOT NULL,
                    applied_at VARCHAR(32) NOT NULL
                )
                """
            )
        )
        known = {
            row[0]
            for row in connection.execute(
                text("SELECT version FROM schema_migrations")
            )
        }
        for version, description, operation in MIGRATIONS:
            if version in known:
                already_applied.append(version)
                continue
            operation(connection)
            connection.execute(
                text(
                    """
                    INSERT INTO schema_migrations(version, description, applied_at)
                    VALUES (:version, :description, :applied_at)
                    """
                ),
                {
                    "version": version,
                    "description": description,
                    "applied_at": _now(),
                },
            )
            applied.append(version)
    return MigrationReport(applied=applied, already_applied=already_applied)


def report_as_dict(report: MigrationReport) -> dict:
    return asdict(report)


def _create_application_schema(connection) -> None:
    Base.metadata.create_all(bind=connection)


def _create_operational_indexes(connection) -> None:
    statements = (
        """
        CREATE INDEX IF NOT EXISTS ix_pipeline_runs_name_started
        ON pipeline_runs(pipeline_name, started_at)
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_source_documents_period_status
        ON source_documents(reference_period, extraction_status)
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_observations_period_level_code
        ON observations(reference_period, geographic_level, geographic_code)
        """,
    )
    for statement in statements:
        connection.execute(text(statement))


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


Migration = tuple[str, str, Callable]
MIGRATIONS: tuple[Migration, ...] = (
    (
        "001_application_schema",
        "Create the operational SQLAlchemy schema",
        _create_application_schema,
    ),
    (
        "002_operational_indexes",
        "Add pipeline, source and observation lookup indexes",
        _create_operational_indexes,
    ),
)
