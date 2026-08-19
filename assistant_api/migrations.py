"""Explicit PostgreSQL migrations owned by the Assistant API."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Engine, text


@dataclass(frozen=True)
class MigrationReport:
    applied: tuple[str, ...]
    already_applied: tuple[str, ...]


_MIGRATIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "001_corpus_chunks",
        (
            "CREATE SCHEMA IF NOT EXISTS assistant",
            """
            CREATE TABLE IF NOT EXISTS assistant.corpus_chunks (
                chunk_id CHAR(64) PRIMARY KEY,
                source_id VARCHAR(200) NOT NULL,
                source_url TEXT NOT NULL,
                source_title TEXT NOT NULL,
                publisher VARCHAR(100) NOT NULL,
                reference_period VARCHAR(100) NOT NULL,
                geographic_scope VARCHAR(200) NOT NULL,
                section TEXT NOT NULL,
                ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
                content TEXT NOT NULL,
                content_sha256 CHAR(64) NOT NULL,
                source_sha256 CHAR(64) NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                indexed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                search_vector TSVECTOR GENERATED ALWAYS AS (
                    setweight(to_tsvector('french', coalesce(source_title, '')), 'A') ||
                    setweight(to_tsvector('french', coalesce(section, '')), 'A') ||
                    setweight(to_tsvector('french', coalesce(content, '')), 'B')
                ) STORED,
                UNIQUE (source_id, ordinal, source_sha256)
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_assistant_chunks_search
            ON assistant.corpus_chunks USING GIN (search_vector)
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_assistant_chunks_source_active
            ON assistant.corpus_chunks (source_id, is_active)
            """,
        ),
    ),
    (
        "002_sql_execution_audit",
        (
            """
            CREATE TABLE IF NOT EXISTS assistant.sql_executions (
                execution_id UUID PRIMARY KEY,
                request_id UUID NOT NULL,
                actor_id VARCHAR(128),
                question TEXT NOT NULL,
                interpretation_json TEXT NOT NULL DEFAULT '{}',
                schema_version VARCHAR(64) NOT NULL,
                generated_sql TEXT NOT NULL,
                validation_status VARCHAR(32) NOT NULL,
                validation_error VARCHAR(512),
                duration_ms INTEGER,
                row_count INTEGER,
                plan_cost DOUBLE PRECISION,
                prompt_version VARCHAR(64) NOT NULL,
                model_version VARCHAR(128) NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_assistant_sql_executions_request
            ON assistant.sql_executions (request_id, created_at)
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_assistant_sql_executions_actor
            ON assistant.sql_executions (actor_id, created_at)
            """,
        ),
    ),
)


def apply_migrations(engine: Engine) -> MigrationReport:
    applied: list[str] = []
    already_applied: list[str] = []
    with engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS assistant"))
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS assistant.schema_migrations (
                    version VARCHAR(64) PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        known = {
            row[0]
            for row in connection.execute(
                text("SELECT version FROM assistant.schema_migrations")
            )
        }
        for version, statements in _MIGRATIONS:
            if version in known:
                already_applied.append(version)
                continue
            for statement in statements:
                connection.execute(text(statement))
            connection.execute(
                text(
                    """
                    INSERT INTO assistant.schema_migrations(version)
                    VALUES (:version)
                    """
                ),
                {"version": version},
            )
            applied.append(version)
    return MigrationReport(tuple(applied), tuple(already_applied))


def migration_versions() -> tuple[str, ...]:
    return tuple(version for version, _ in _MIGRATIONS)
