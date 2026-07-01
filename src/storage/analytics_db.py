"""Build a coherent analytical SQLite database from curated BDF and INSEE data."""

from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

DEFAULT_BDF_CURATED = Path("data/processed/statinfo_departements_bi_curated.csv")
DEFAULT_INSEE_MACRO = Path("data/processed/insee_macro/gold/2026/insee_macro_departements_long.csv")
DEFAULT_OUTPUT_DB = Path("data/processed/analytics/surendettement_macro_analytics.db")
DATABASE_VERSION = "surendettement_macro_analytics_v1"


def build_analytics_database(
    bdf_curated_path: Path = DEFAULT_BDF_CURATED,
    insee_macro_path: Path = DEFAULT_INSEE_MACRO,
    output_db: Path = DEFAULT_OUTPUT_DB,
) -> dict[str, int]:
    output_db.parent.mkdir(parents=True, exist_ok=True)
    bdf = _load_bdf_curated(bdf_curated_path)
    insee = _load_insee_macro(insee_macro_path)
    departments = _build_departments_dimension(bdf=bdf, insee=insee)
    indicators = _build_indicator_dimension(bdf=bdf, insee=insee)

    with sqlite3.connect(output_db) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        _drop_existing_objects(connection)
        _create_schema(connection)
        _write_frame(connection, "dim_department", departments)
        _write_frame(connection, "dim_indicator", indicators)
        _write_frame(connection, "fact_bdf_statinfo", _build_bdf_fact(bdf))
        _write_frame(connection, "fact_insee_macro", _build_insee_fact(insee))
        _write_frame(connection, "pipeline_metadata", _build_metadata(bdf_curated_path, insee_macro_path))
        _create_indexes(connection)
        _create_views(connection)
        connection.commit()

        return {
            "departments": _count_rows(connection, "dim_department"),
            "indicators": _count_rows(connection, "dim_indicator"),
            "bdf_rows": _count_rows(connection, "fact_bdf_statinfo"),
            "insee_rows": _count_rows(connection, "fact_insee_macro"),
        }


def _load_bdf_curated(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"departement_code": str})
    required = {
        "reference_period",
        "reference_year",
        "reference_month_number",
        "region",
        "departement_code",
        "departement_name",
        "indicator_code",
        "indicator_name",
        "indicator_group",
        "unit",
        "value",
        "source_file",
    }
    _check_required_columns(df, required, path)
    df["departement_code"] = df["departement_code"].map(_standardize_department_code)
    return df


def _load_insee_macro(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"departement_code": str})
    required = {
        "reference_year",
        "departement_code",
        "indicator_code",
        "indicator_name",
        "indicator_group",
        "aggregation_rule",
        "value",
        "source_dataset",
    }
    _check_required_columns(df, required, path)
    df["departement_code"] = df["departement_code"].map(_standardize_department_code)
    return df


def _build_departments_dimension(bdf: pd.DataFrame, insee: pd.DataFrame) -> pd.DataFrame:
    bdf_deps = (
        bdf[["departement_code", "departement_name", "region"]]
        .dropna(subset=["departement_code"])
        .drop_duplicates("departement_code")
        .rename(columns={"region": "region_name"})
    )
    insee_deps = (
        insee[["departement_code", "departement_name"]]
        .dropna(subset=["departement_code"])
        .drop_duplicates("departement_code")
    )
    departments = insee_deps.merge(bdf_deps, on="departement_code", how="outer", suffixes=("_insee", "_bdf"))
    departments["departement_name"] = departments["departement_name_bdf"].combine_first(
        departments["departement_name_insee"]
    )
    departments["is_metropolitan_scope"] = True
    return departments[
        ["departement_code", "departement_name", "region_name", "is_metropolitan_scope"]
    ].sort_values("departement_code")


def _build_indicator_dimension(bdf: pd.DataFrame, insee: pd.DataFrame) -> pd.DataFrame:
    bdf_indicators = (
        bdf[["indicator_code", "indicator_name", "indicator_group", "unit"]]
        .drop_duplicates("indicator_code")
        .assign(source_system="bdf_statinfo", aggregation_rule=pd.NA)
    )
    insee_indicators = (
        insee[["indicator_code", "indicator_name", "indicator_group", "aggregation_rule"]]
        .drop_duplicates("indicator_code")
        .assign(source_system="insee_macro", unit=pd.NA)
    )
    indicators = pd.concat([bdf_indicators, insee_indicators], ignore_index=True)
    indicators["indicator_key"] = indicators["source_system"] + ":" + indicators["indicator_code"].astype(str)
    return indicators[
        [
            "indicator_key",
            "source_system",
            "indicator_code",
            "indicator_name",
            "indicator_group",
            "unit",
            "aggregation_rule",
        ]
    ].sort_values(["source_system", "indicator_code"])


def _build_bdf_fact(bdf: pd.DataFrame) -> pd.DataFrame:
    fact = bdf.copy()
    fact["indicator_key"] = "bdf_statinfo:" + fact["indicator_code"].astype(str)
    fact["value"] = pd.to_numeric(fact["value"], errors="coerce")
    return fact[
        [
            "reference_period",
            "reference_year",
            "reference_month_number",
            "departement_code",
            "indicator_key",
            "value",
            "source_file",
            "pipeline_version",
        ]
    ]


def _build_insee_fact(insee: pd.DataFrame) -> pd.DataFrame:
    fact = insee.copy()
    fact["indicator_key"] = "insee_macro:" + fact["indicator_code"].astype(str)
    fact["value"] = pd.to_numeric(fact["value"], errors="coerce")
    return fact[
        [
            "reference_year",
            "departement_code",
            "indicator_key",
            "value",
            "source_dataset",
            "pipeline_version",
        ]
    ]


def _build_metadata(bdf_path: Path, insee_path: Path) -> pd.DataFrame:
    built_at = datetime.now(timezone.utc).isoformat()
    return pd.DataFrame(
        [
            {
                "database_version": DATABASE_VERSION,
                "source_system": "bdf_statinfo",
                "source_path": str(bdf_path),
                "built_at": built_at,
            },
            {
                "database_version": DATABASE_VERSION,
                "source_system": "insee_macro",
                "source_path": str(insee_path),
                "built_at": built_at,
            },
        ]
    )


def _drop_existing_objects(connection: sqlite3.Connection) -> None:
    objects = [
        "v_bdf_total_deposits",
        "v_bdf_total_deposits_with_insee_macro",
        "pipeline_metadata",
        "fact_insee_macro",
        "fact_bdf_statinfo",
        "dim_indicator",
        "dim_department",
    ]
    for name in objects:
        connection.execute(f"DROP VIEW IF EXISTS {name}")
        connection.execute(f"DROP TABLE IF EXISTS {name}")


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE dim_department (
            departement_code TEXT PRIMARY KEY,
            departement_name TEXT,
            region_name TEXT,
            is_metropolitan_scope INTEGER NOT NULL
        );

        CREATE TABLE dim_indicator (
            indicator_key TEXT PRIMARY KEY,
            source_system TEXT NOT NULL,
            indicator_code TEXT NOT NULL,
            indicator_name TEXT,
            indicator_group TEXT,
            unit TEXT,
            aggregation_rule TEXT
        );

        CREATE TABLE fact_bdf_statinfo (
            reference_period TEXT NOT NULL,
            reference_year INTEGER NOT NULL,
            reference_month_number INTEGER NOT NULL,
            departement_code TEXT NOT NULL,
            indicator_key TEXT NOT NULL,
            value REAL NOT NULL,
            source_file TEXT,
            pipeline_version TEXT,
            FOREIGN KEY (departement_code) REFERENCES dim_department(departement_code),
            FOREIGN KEY (indicator_key) REFERENCES dim_indicator(indicator_key)
        );

        CREATE TABLE fact_insee_macro (
            reference_year INTEGER NOT NULL,
            departement_code TEXT NOT NULL,
            indicator_key TEXT NOT NULL,
            value REAL NOT NULL,
            source_dataset TEXT,
            pipeline_version TEXT,
            FOREIGN KEY (departement_code) REFERENCES dim_department(departement_code),
            FOREIGN KEY (indicator_key) REFERENCES dim_indicator(indicator_key)
        );

        CREATE TABLE pipeline_metadata (
            database_version TEXT NOT NULL,
            source_system TEXT NOT NULL,
            source_path TEXT NOT NULL,
            built_at TEXT NOT NULL
        );
        """
    )


def _create_indexes(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE INDEX idx_bdf_department_period ON fact_bdf_statinfo(departement_code, reference_period);
        CREATE INDEX idx_bdf_indicator ON fact_bdf_statinfo(indicator_key);
        CREATE INDEX idx_insee_department_year ON fact_insee_macro(departement_code, reference_year);
        CREATE INDEX idx_insee_indicator ON fact_insee_macro(indicator_key);
        CREATE UNIQUE INDEX uq_bdf_fact
            ON fact_bdf_statinfo(reference_period, departement_code, indicator_key);
        CREATE UNIQUE INDEX uq_insee_fact
            ON fact_insee_macro(reference_year, departement_code, indicator_key);
        """
    )


def _create_views(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE VIEW v_bdf_total_deposits AS
        SELECT
            b.reference_period,
            b.reference_year,
            b.reference_month_number,
            b.departement_code,
            d.departement_name,
            d.region_name,
            b.value AS bdf_total_deposits_value
        FROM fact_bdf_statinfo b
        JOIN dim_indicator i ON i.indicator_key = b.indicator_key
        LEFT JOIN dim_department d ON d.departement_code = b.departement_code
        WHERE i.source_system = 'bdf_statinfo'
          AND i.indicator_code = 'total';

        CREATE VIEW v_bdf_total_deposits_with_insee_macro AS
        SELECT
            b.reference_period AS bdf_reference_period,
            b.reference_year AS bdf_reference_year,
            b.reference_month_number AS bdf_reference_month_number,
            b.departement_code,
            b.departement_name,
            b.region_name,
            b.bdf_total_deposits_value,
            m.reference_year AS macro_reference_year,
            i.indicator_code AS macro_indicator_code,
            i.indicator_name AS macro_indicator_name,
            i.indicator_group AS macro_indicator_group,
            m.value AS macro_value
        FROM v_bdf_total_deposits b
        JOIN fact_insee_macro m
          ON m.departement_code = b.departement_code
         AND m.reference_year = (
             SELECT MAX(reference_year)
             FROM fact_insee_macro
             WHERE reference_year <= b.reference_year + 1
         )
        JOIN dim_indicator i ON i.indicator_key = m.indicator_key
        WHERE i.source_system = 'insee_macro';
        """
    )


def _write_frame(connection: sqlite3.Connection, table_name: str, frame: pd.DataFrame) -> None:
    frame.to_sql(table_name, connection, if_exists="append", index=False)


def _count_rows(connection: sqlite3.Connection, table_name: str) -> int:
    return int(connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


def _check_required_columns(df: pd.DataFrame, columns: set[str], path: Path) -> None:
    missing = sorted(columns - set(df.columns))
    if missing:
        raise ValueError(f"Missing columns in {path}: {', '.join(missing)}")


def _standardize_department_code(value: object) -> str:
    text = str(value).strip().upper()
    return text.zfill(2) if text.isdigit() else text


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the analytical SQLite database.")
    parser.add_argument("--bdf-curated", default=str(DEFAULT_BDF_CURATED))
    parser.add_argument("--insee-macro", default=str(DEFAULT_INSEE_MACRO))
    parser.add_argument("--output-db", default=str(DEFAULT_OUTPUT_DB))
    return parser


def main() -> None:
    args = _build_arg_parser().parse_args()
    summary = build_analytics_database(
        bdf_curated_path=Path(args.bdf_curated),
        insee_macro_path=Path(args.insee_macro),
        output_db=Path(args.output_db),
    )
    print(
        "Analytics database built | "
        f"departments={summary['departments']} "
        f"indicators={summary['indicators']} "
        f"bdf_rows={summary['bdf_rows']} "
        f"insee_rows={summary['insee_rows']}"
    )


if __name__ == "__main__":
    main()
