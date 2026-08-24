"""Idempotently transfer the legacy analytical SQLite mart to PostgreSQL."""

from __future__ import annotations

import argparse
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from sqlalchemy import MetaData, create_engine, func, select, text
from sqlalchemy.dialects.postgresql import insert as postgresql_insert

from src.storage.schema_migrations import _create_macro_region_analytics_view


TABLES = (
    "dim_region",
    "dim_period",
    "dim_department",
    "dim_indicator",
    "fact_bdf_statinfo",
    "fact_surendettement",
    "fact_insee_macro",
    "pipeline_metadata",
    "schema_deprecations",
    "fact_macro_override",
)
VIEWS = (
    "v_bdf_total_deposits",
    "v_surendettement_annual",
    "v_bdf_total_deposits_with_insee_macro",
    "v_surendettement_with_insee_macro",
    "v_insee_macro_region",
    "v_insee_macro_region_selected",
)
BATCH_SIZE = 500


@dataclass(slots=True)
class AnalyticsMigrationReport:
    source: str
    inserted_by_table: dict[str, int]
    skipped_by_table: dict[str, int]
    views: list[str]


def migrate_analytics(
    source_path: Path,
    target_url: str,
    *,
    replace_snapshot: bool = False,
) -> AnalyticsMigrationReport:
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    source_engine = create_engine(f"sqlite:///{source_path}")
    target_engine = create_engine(target_url)
    if target_engine.dialect.name != "postgresql":
        raise ValueError("Target database must be PostgreSQL")

    source_metadata = MetaData()
    source_metadata.reflect(bind=source_engine, only=TABLES)
    source_metadata.create_all(target_engine, checkfirst=True)
    target_metadata = MetaData()
    target_metadata.reflect(bind=target_engine, only=TABLES)
    inserted_by_table: dict[str, int] = {}
    skipped_by_table: dict[str, int] = {}

    with source_engine.connect() as source, target_engine.begin() as target:
        if replace_snapshot:
            for name in (
                "fact_bdf_statinfo",
                "fact_surendettement",
                "fact_insee_macro",
                "pipeline_metadata",
            ):
                target.execute(target_metadata.tables[name].delete())
        for name in TABLES:
            source_table = source_metadata.tables[name]
            target_table = target_metadata.tables[name]
            before = target.execute(
                select(func.count()).select_from(target_table)
            ).scalar_one()
            target_columns = set(target_table.c.keys())
            rows = [
                {
                    key: value
                    for key, value in dict(row._mapping).items()
                    if key in target_columns
                }
                for row in source.execute(select(source_table))
            ]
            if name == "pipeline_metadata" and before and not replace_snapshot:
                inserted_by_table[name] = 0
                skipped_by_table[name] = len(rows)
                continue
            if not rows:
                inserted_by_table[name] = 0
                skipped_by_table[name] = 0
                continue
            for start in range(0, len(rows), BATCH_SIZE):
                batch = rows[start : start + BATCH_SIZE]
                target.execute(
                    postgresql_insert(target_table)
                    .values(batch)
                    .on_conflict_do_nothing()
                )
            after = target.execute(
                select(func.count()).select_from(target_table)
            ).scalar_one()
            inserted = after - before
            inserted_by_table[name] = inserted
            skipped_by_table[name] = len(rows) - inserted

        target.execute(text("DROP VIEW IF EXISTS analytics_macro_regions"))
        for name in reversed(VIEWS):
            target.execute(text(f"DROP VIEW IF EXISTS {name}"))
        for name in VIEWS:
            definition = source.execute(
                text(
                    "SELECT sql FROM sqlite_master "
                    "WHERE type = 'view' AND name = :name"
                ),
                {"name": name},
            ).scalar_one()
            target.execute(text(definition))
        _create_macro_region_analytics_view(target)

    return AnalyticsMigrationReport(
        source=str(source_path),
        inserted_by_table=inserted_by_table,
        skipped_by_table=skipped_by_table,
        views=list(VIEWS),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="migrate-analytics-to-postgres")
    parser.add_argument(
        "--source",
        type=Path,
        default=Path(
            "data/processed/analytics/surendettement_macro_analytics.db"
        ),
    )
    parser.add_argument("--replace-snapshot", action="store_true")
    parser.add_argument(
        "--target-url",
        default=os.getenv("ADMIN_DATABASE_URL") or os.getenv("DATABASE_URL"),
    )
    args = parser.parse_args(argv)
    if os.getenv("CONFIRM_ANALYTICS_MIGRATION") != "yes":
        parser.error("CONFIRM_ANALYTICS_MIGRATION=yes is required")
    if not args.target_url:
        parser.error("--target-url, ADMIN_DATABASE_URL or DATABASE_URL is required")
    report = migrate_analytics(
        args.source,
        args.target_url,
        replace_snapshot=args.replace_snapshot,
    )
    print(asdict(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
