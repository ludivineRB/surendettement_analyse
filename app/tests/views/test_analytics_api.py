import sqlite3
from pathlib import Path

from app.core.config import settings
from app.schemas.analytics import MacroOverrideCreate, MacroOverrideUpdate
from app.views.analytics_api import create_macro_override, health, list_joined_data, update_macro_override


def _create_test_analytics_db(path: Path) -> None:
    with sqlite3.connect(path) as connection:
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
                pipeline_version TEXT
            );
            CREATE TABLE fact_insee_macro (
                reference_year INTEGER NOT NULL,
                departement_code TEXT NOT NULL,
                indicator_key TEXT NOT NULL,
                value REAL NOT NULL,
                source_dataset TEXT,
                pipeline_version TEXT
            );
            CREATE VIEW v_bdf_total_deposits_with_insee_macro AS
            SELECT
                b.reference_period AS bdf_reference_period,
                b.reference_year AS bdf_reference_year,
                b.reference_month_number AS bdf_reference_month_number,
                b.departement_code,
                d.departement_name,
                d.region_name,
                b.value AS bdf_total_deposits_value,
                m.reference_year AS macro_reference_year,
                i.indicator_code AS macro_indicator_code,
                i.indicator_name AS macro_indicator_name,
                i.indicator_group AS macro_indicator_group,
                m.value AS macro_value
            FROM fact_bdf_statinfo b
            JOIN fact_insee_macro m ON m.departement_code = b.departement_code
            JOIN dim_indicator i ON i.indicator_key = m.indicator_key
            JOIN dim_department d ON d.departement_code = b.departement_code;
            """
        )
        connection.execute("INSERT INTO dim_department VALUES ('75', 'Paris', 'Ile de France', 1)")
        connection.execute(
            "INSERT INTO dim_indicator VALUES "
            "('bdf_statinfo:total', 'bdf_statinfo', 'total', 'TOTAL', 'total', 'milliards_euros', NULL)"
        )
        connection.execute(
            "INSERT INTO dim_indicator VALUES "
            "('insee_macro:P22_POP', 'insee_macro', 'P22_POP', 'Population', 'démographie', NULL, 'sum')"
        )
        connection.execute(
            "INSERT INTO fact_bdf_statinfo VALUES "
            "('2025-08', 2025, 8, '75', 'bdf_statinfo:total', 568.6, 'bdf.pdf', 'test')"
        )
        connection.execute(
            "INSERT INTO fact_insee_macro VALUES "
            "(2026, '75', 'insee_macro:P22_POP', 2100000, 'insee', 'test')"
        )


def test_analytics_api_reads_joined_data_and_creates_override(tmp_path: Path):
    db_path = tmp_path / "analytics.db"
    _create_test_analytics_db(db_path)
    original_path = settings.ANALYTICS_DB_PATH
    settings.ANALYTICS_DB_PATH = str(db_path)
    try:
        assert health()["status"] == "ok"
        joined = list_joined_data(departement_code="75", limit=500, offset=0)
        assert joined[0]["macro_indicator_code"] == "P22_POP"

        created = create_macro_override(
            MacroOverrideCreate(
                reference_year=2026,
                departement_code="75",
                indicator_code="custom_indicator",
                indicator_name="Custom indicator",
                value=42.0,
                source_note="manual test",
            )
        )
        override_id = created["id"]

        updated = update_macro_override(override_id, MacroOverrideUpdate(value=43.0))
        assert updated["value"] == 43.0
    finally:
        settings.ANALYTICS_DB_PATH = original_path
