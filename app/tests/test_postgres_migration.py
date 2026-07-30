"""Opt-in integration tests for the SQLite-to-PostgreSQL migration."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

import pytest
from sqlalchemy import MetaData, create_engine, func, select, text

from src.storage.migrate_to_postgres import (
    DEFAULT_BATCH_SIZE,
    _iter_batches,
    migrate_sqlite_to_postgres,
)
from src.storage.schema_migrations import apply_migrations


pytestmark = pytest.mark.postgres_integration
SOURCE_DB = Path("data/processed/surendettement.db")


def test_rows_are_split_into_bounded_batches():
    rows = [{"id": index} for index in range(DEFAULT_BATCH_SIZE * 2 + 1)]
    batches = list(_iter_batches(rows, DEFAULT_BATCH_SIZE))
    assert [len(batch) for batch in batches] == [
        DEFAULT_BATCH_SIZE,
        DEFAULT_BATCH_SIZE,
        1,
    ]
    assert [row for batch in batches for row in batch] == rows
    with pytest.raises(ValueError, match="greater than zero"):
        list(_iter_batches(rows, 0))


@pytest.fixture(scope="module")
def postgres_url() -> str:
    url = os.getenv("TEST_POSTGRES_DATABASE_URL")
    if not url:
        pytest.skip("TEST_POSTGRES_DATABASE_URL is not configured")
    parsed = urlparse(url.replace("postgresql+psycopg://", "postgresql://", 1))
    database_name = parsed.path.lstrip("/").lower()
    if not any(marker in database_name for marker in ("local", "staging", "test")):
        pytest.fail(
            "Refusing PostgreSQL integration tests: database name must contain "
            "'local', 'staging', or 'test'"
        )
    return url


@pytest.fixture(scope="module")
def migrated_database(postgres_url: str):
    if not SOURCE_DB.is_file():
        pytest.fail(f"SQLite source does not exist: {SOURCE_DB}")
    first = migrate_sqlite_to_postgres(
        source_path=SOURCE_DB,
        target_url=postgres_url,
    )
    return postgres_url, first


def _table_counts(url: str) -> dict[str, int]:
    engine = create_engine(url)
    metadata = MetaData()
    metadata.reflect(bind=engine)
    with engine.connect() as connection:
        return {
            name: connection.execute(
                select(func.count()).select_from(table)
            ).scalar_one()
            for name, table in metadata.tables.items()
            if name != "schema_migrations"
        }


def test_postgres_connection_and_migrations_are_idempotent(postgres_url: str):
    engine = create_engine(postgres_url)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT 1")).scalar_one() == 1
    first = apply_migrations(engine)
    second = apply_migrations(engine)
    assert second.applied == []
    assert set(first.applied + first.already_applied) == set(second.already_applied)


def test_transfer_is_idempotent(migrated_database):
    postgres_url, first = migrated_database
    counts_before = _table_counts(postgres_url)
    second = migrate_sqlite_to_postgres(
        source_path=SOURCE_DB,
        target_url=postgres_url,
    )
    counts_after = _table_counts(postgres_url)
    assert counts_after == counts_before
    assert all(inserted == 0 for inserted in second.inserted_by_table.values())
    assert first.target_dialect == "postgresql"


def test_existing_row_is_not_overwritten(migrated_database):
    postgres_url, _ = migrated_database
    engine = create_engine(postgres_url)
    marker = "postgres-integration-preserved"
    with engine.begin() as connection:
        row_id = connection.execute(
            text("SELECT id FROM surendettement_data ORDER BY id LIMIT 1")
        ).scalar_one()
        original = connection.execute(
            text("SELECT source_file FROM surendettement_data WHERE id = :id"),
            {"id": row_id},
        ).scalar_one()
        connection.execute(
            text(
                "UPDATE surendettement_data "
                "SET source_file = :marker WHERE id = :id"
            ),
            {"marker": marker, "id": row_id},
        )
    try:
        migrate_sqlite_to_postgres(
            source_path=SOURCE_DB,
            target_url=postgres_url,
        )
        with engine.connect() as connection:
            preserved = connection.execute(
                text("SELECT source_file FROM surendettement_data WHERE id = :id"),
                {"id": row_id},
            ).scalar_one()
        assert preserved == marker
    finally:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE surendettement_data "
                    "SET source_file = :original WHERE id = :id"
                ),
                {"original": original, "id": row_id},
            )


def test_postgres_sequences_are_ahead_of_primary_keys(migrated_database):
    postgres_url, _ = migrated_database
    engine = create_engine(postgres_url)
    metadata = MetaData()
    metadata.reflect(bind=engine)
    with engine.connect() as connection:
        for table in metadata.sorted_tables:
            integer_keys = [
                column
                for column in table.primary_key
                if column.autoincrement is True or column.autoincrement == "auto"
            ]
            if len(integer_keys) != 1:
                continue
            column = integer_keys[0]
            sequence = connection.execute(
                text("SELECT pg_get_serial_sequence(:table, :column)"),
                {"table": table.name, "column": column.name},
            ).scalar_one_or_none()
            if sequence is None:
                continue
            maximum = connection.execute(select(func.max(column))).scalar_one() or 0
            last_value = connection.execute(
                text(f"SELECT last_value FROM {sequence}")
            ).scalar_one()
            assert last_value >= maximum, table.name


def test_sqlite_and_postgres_table_volumes_match(migrated_database):
    postgres_url, _ = migrated_database
    source_counts = _table_counts(f"sqlite:///{SOURCE_DB}")
    target_counts = _table_counts(postgres_url)
    common = set(source_counts) & set(target_counts)
    assert common
    assert {
        table: (source_counts[table], target_counts[table])
        for table in common
        if source_counts[table] != target_counts[table]
    } == {}


def test_dry_run_does_not_change_volumes(migrated_database):
    postgres_url, _ = migrated_database
    before = _table_counts(postgres_url)
    report = migrate_sqlite_to_postgres(
        source_path=SOURCE_DB,
        target_url=postgres_url,
        dry_run=True,
    )
    after = _table_counts(postgres_url)
    assert after == before
    assert all(inserted == 0 for inserted in report.inserted_by_table.values())
