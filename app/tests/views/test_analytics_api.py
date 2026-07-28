import sqlite3
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.schemas.analytics import MacroOverrideCreate, MacroOverrideUpdate
from src.storage.models import Base, InclusionIndicator, InclusionObservation, InclusionSourceDocument
from app.views.analytics_api import (
    create_macro_override,
    health,
    list_inclusion_financiere,
    list_macro_economic_data,
    list_regional_macro_economic_data,
    list_surendettement_data,
    list_joined_data,
    streamlit_dataset,
    update_macro_override,
)


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
            CREATE TABLE fact_surendettement (
                reference_year INTEGER NOT NULL,
                departement_code TEXT NOT NULL,
                indicator_key TEXT NOT NULL,
                value REAL NOT NULL,
                source_file TEXT
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
            CREATE VIEW v_surendettement_with_insee_macro AS
            SELECT
                s.reference_year,
                s.departement_code,
                d.departement_name,
                d.region_name,
                SUM(s.value) AS surendettement_value,
                m.reference_year AS macro_reference_year,
                i.indicator_code AS macro_indicator_code,
                i.indicator_name AS macro_indicator_name,
                i.indicator_group AS macro_indicator_group,
                m.value AS macro_value
            FROM fact_surendettement s
            JOIN fact_insee_macro m ON m.departement_code = s.departement_code
            JOIN dim_indicator i ON i.indicator_key = m.indicator_key
            JOIN dim_department d ON d.departement_code = s.departement_code
            GROUP BY s.reference_year, s.departement_code, d.departement_name, d.region_name,
                     m.reference_year, i.indicator_code, i.indicator_name, i.indicator_group, m.value;
            CREATE VIEW v_insee_macro_region_selected AS
            SELECT 2022 AS reference_year,
                   'Île-de-France' AS region_name,
                   'P22_POP' AS indicator_code,
                   'Population' AS indicator_name,
                   'démographie' AS indicator_group,
                   'sum' AS aggregation_rule,
                   12260000.0 AS value;
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
            "INSERT INTO dim_indicator VALUES "
            "('surendettement:surendettement_dossiers', 'surendettement', "
            "'surendettement_dossiers', 'Dossiers de surendettement', 'surendettement', NULL, 'sum')"
        )
        connection.execute(
            "INSERT INTO fact_bdf_statinfo VALUES "
            "('2025-08', 2025, 8, '75', 'bdf_statinfo:total', 568.6, 'bdf.pdf', 'test')"
        )
        connection.execute(
            "INSERT INTO fact_insee_macro VALUES "
            "(2026, '75', 'insee_macro:P22_POP', 2100000, 'insee', 'test')"
        )
        connection.execute(
            "INSERT INTO fact_surendettement VALUES "
            "(2025, '75', 'surendettement:surendettement_dossiers', 123, 'sur.pdf')"
        )


def test_analytics_api_reads_joined_data_and_creates_override(tmp_path: Path):
    db_path = tmp_path / "analytics.db"
    _create_test_analytics_db(db_path)
    original_path = settings.ANALYTICS_DB_PATH
    settings.ANALYTICS_DB_PATH = str(db_path)
    try:
        assert health()["status"] == "ok"
        surendettement = list_surendettement_data(departement_code="75", limit=500, offset=0)
        assert surendettement[0]["indicator_code"] == "surendettement_dossiers"
        assert surendettement[0]["surendettement_value"] == 123
        assert surendettement[0]["dossiers_deposes"] == 123

        macro = list_macro_economic_data(departement_code="75", limit=500, offset=0)
        assert macro[0]["indicator_code"] == "P22_POP"
        assert macro[0]["macro_value"] == 2_100_000

        regional_macro = list_regional_macro_economic_data(
            region_name="Île-de-France",
            indicator_code="P22_POP",
            reference_year=2022,
            limit=500,
            offset=0,
        )
        assert regional_macro[0]["value"] == 12_260_000

        joined = list_joined_data(departement_code="75", limit=500, offset=0)
        assert joined[0]["macro_indicator_code"] == "P22_POP"

        streamlit_rows = streamlit_dataset(departement_code="75", limit=500, offset=0)
        assert streamlit_rows[0]["indicator_code"] == "P22_POP"
        assert streamlit_rows[0]["macro_value"] == 2_100_000
        assert streamlit_rows[0]["surendettement_value"] == 123
        assert streamlit_rows[0]["dossiers_deposes"] == 123

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


def test_inclusion_financiere_api_filters_monthly_regional_data(tmp_path: Path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'inclusion.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        indicator = InclusionIndicator(
            code="surendettement_dossiers_deposes",
            label="Dossiers de surendettement déposés",
        )
        document = InclusionSourceDocument(
            source_name="Banque de France",
            publication_type="barometre_mensuel_inclusion_financiere",
            region_code="94",
            region_name="Corse",
            reference_period="2025-06",
            page_url="https://example.test/page",
            pdf_url="https://example.test/source.pdf",
            pdf_filename="source.pdf",
            pdf_sha256="a" * 64,
            storage_path="source.pdf",
            extraction_status="success",
            extractor_version="test",
        )
        session.add_all([indicator, document])
        session.flush()
        session.add(
            InclusionObservation(
                source_document_id=document.id,
                indicator_id=indicator.id,
                idempotence_key="b" * 64,
                indicator_code=indicator.code,
                region_code="94",
                reference_period="2025-06",
                geographic_level="region",
                geographic_code="94",
                geographic_name="Corse",
                value_numeric=123.0,
                unit="dossiers",
                observation_type="monthly",
                page_number=1,
                extraction_method="native_text",
                confidence_score=0.86,
            )
        )
        session.commit()

    monkeypatch.setattr("app.views.analytics_api.get_session_factory", lambda: factory)
    rows = list_inclusion_financiere(
        region_code="94",
        indicator_code="surendettement_dossiers_deposes",
        from_period="2025-01",
        to_period="2025-12",
        limit=100,
        offset=0,
    )

    assert rows == [
        {
            "reference_period": "2025-06",
            "region_code": "94",
            "region_name": "Corse",
            "indicator_code": "surendettement_dossiers_deposes",
            "indicator_label": "Dossiers de surendettement déposés",
            "value": 123.0,
            "unit": "dossiers",
            "observation_type": "monthly",
            "confidence_score": 0.86,
            "page_number": 1,
            "page_url": "https://example.test/page",
            "pdf_url": "https://example.test/source.pdf",
        }
    ]
