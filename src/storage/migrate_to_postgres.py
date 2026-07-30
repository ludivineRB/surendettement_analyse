"""Copy the operational SQLite database to PostgreSQL without overwriting rows."""

from __future__ import annotations

import argparse
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from sqlalchemy import Integer, MetaData, create_engine, select, text
from sqlalchemy.dialects.postgresql import insert as postgresql_insert

from src.storage.models import Base
from src.storage.schema_migrations import apply_migrations


DEFAULT_BATCH_SIZE = 500


@dataclass(slots=True)
class DatabaseCopyReport:
    source: str
    target_dialect: str
    inserted_by_table: dict[str, int] = field(default_factory=dict)
    skipped_by_table: dict[str, int] = field(default_factory=dict)


def migrate_sqlite_to_postgres(
    *,
    source_path: Path,
    target_url: str,
    dry_run: bool = False,
) -> DatabaseCopyReport:
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    target_engine = create_engine(target_url)
    if target_engine.dialect.name != "postgresql":
        raise ValueError("Target database must be PostgreSQL")
    source_engine = create_engine(f"sqlite:///{source_path}")
    apply_migrations(target_engine)
    report = DatabaseCopyReport(
        source=str(source_path),
        target_dialect=target_engine.dialect.name,
    )
    source_metadata = MetaData()
    source_metadata.reflect(bind=source_engine)
    target_tables = {table.name: table for table in Base.metadata.sorted_tables}
    with source_engine.connect() as source, target_engine.begin() as target:
        target_tables_with_migrations = {
            **target_tables,
            "schema_migrations": Base.metadata.tables.get("schema_migrations"),
        }
        for table_name in _copy_order(target_tables):
            if table_name not in source_metadata.tables:
                continue
            source_table = source_metadata.tables[table_name]
            target_table = target_tables_with_migrations[table_name]
            rows = [dict(row._mapping) for row in source.execute(select(source_table))]
            if dry_run or not rows:
                report.inserted_by_table[table_name] = 0
                report.skipped_by_table[table_name] = len(rows)
                continue
            primary_keys = [column.name for column in target_table.primary_key]
            inserted = 0
            for batch in _iter_batches(rows, DEFAULT_BATCH_SIZE):
                statement = postgresql_insert(target_table).values(batch)
                if primary_keys:
                    statement = statement.on_conflict_do_nothing(
                        index_elements=primary_keys
                    )
                result = target.execute(statement)
                inserted += max(result.rowcount or 0, 0)
            report.inserted_by_table[table_name] = inserted
            report.skipped_by_table[table_name] = len(rows) - inserted
            _reset_postgres_sequence(target, target_table)
    return report


def _iter_batches(rows: list[dict], batch_size: int):
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero")
    for start in range(0, len(rows), batch_size):
        yield rows[start : start + batch_size]


def _copy_order(tables: dict) -> list[str]:
    return [
        table.name
        for table in Base.metadata.sorted_tables
        if table.name in tables and table.name != "schema_migrations"
    ]


def _reset_postgres_sequence(connection, table) -> None:
    integer_primary_keys = [
        column
        for column in table.primary_key
        if isinstance(column.type, Integer)
        and (column.autoincrement is True or column.autoincrement == "auto")
    ]
    if len(integer_primary_keys) != 1:
        return
    column = integer_primary_keys[0]
    connection.execute(
        text(
            "SELECT setval(pg_get_serial_sequence(:table_name, :column_name), "
            f"COALESCE((SELECT MAX({column.name}) FROM {table.name}), 1), true)"
        ),
        {"table_name": table.name, "column_name": column.name},
    )


def report_as_dict(report: DatabaseCopyReport) -> dict:
    return asdict(report)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="migrate-to-postgres")
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("data/processed/surendettement.db"),
    )
    parser.add_argument(
        "--target-url",
        default=os.getenv("TARGET_DATABASE_URL"),
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if not args.target_url:
        parser.error("--target-url or TARGET_DATABASE_URL is required")
    report = migrate_sqlite_to_postgres(
        source_path=args.source,
        target_url=args.target_url,
        dry_run=args.dry_run,
    )
    print(report_as_dict(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
