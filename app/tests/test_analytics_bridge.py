import sqlite3

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from src.risk_score.analytics_bridge import (
    BRIDGE_VERSION,
    import_analytics_indicators,
)
from src.risk_score.service import RiskScoreCalculator
from src.storage.models import (
    Base,
    InclusionIndicator,
    InclusionObservation,
    InclusionSourceDocument,
    RiskScoreIndicatorConfig,
    RiskScoreModel,
)


def _analytics_fixture(path):
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
                indicator_code TEXT NOT NULL
            );
            CREATE TABLE fact_insee_macro (
                reference_year INTEGER NOT NULL,
                departement_code TEXT NOT NULL,
                indicator_key TEXT NOT NULL,
                value REAL NOT NULL
            );
            """
        )
        connection.executemany(
            "INSERT INTO dim_department VALUES (?, ?, ?, 1)",
            [
                ("01", "Ain", "Auvergne-Rhône-Alpes"),
                ("03", "Allier", "Auvergne-Rhône-Alpes"),
            ],
        )
        connection.executemany(
            "INSERT INTO dim_indicator VALUES (?, ?)",
            [
                ("pop", "P22_POP"),
                ("active", "P22_ACT1564"),
                ("unemployed", "P22_CHOM1564"),
            ],
        )
        for department, population, active, unemployed in (
            ("01", 1000, 500, 50),
            ("03", 3000, 1000, 200),
        ):
            connection.executemany(
                "INSERT INTO fact_insee_macro VALUES (2022, ?, ?, ?)",
                [
                    (department, "pop", population),
                    (department, "active", active),
                    (department, "unemployed", unemployed),
                ],
            )


def _operational_factory(path):
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        indicator = InclusionIndicator(
            code="surendettement_dossiers_deposes",
            label="Dossiers",
            category="test",
            default_unit="dossiers",
        )
        session.add(indicator)
        document = InclusionSourceDocument(
            source_name="Fixture",
            publication_type="barometre",
            region_code="84",
            region_name="Auvergne-Rhône-Alpes",
            reference_period="2025-06",
            page_url="https://example.test/page",
            pdf_url="https://example.test/file.pdf",
            pdf_filename="file.pdf",
            pdf_sha256="a" * 64,
            storage_path="file.pdf",
            extraction_status="success",
            extractor_version="fixture",
        )
        session.add(document)
        session.flush()
        session.add(
            InclusionObservation(
                source_document_id=document.id,
                indicator_id=indicator.id,
                idempotence_key="b" * 64,
                indicator_code=indicator.code,
                region_code="84",
                reference_period="2025-06",
                geographic_level="region",
                geographic_code="84",
                geographic_name="Auvergne-Rhône-Alpes",
                value_numeric=8,
                unit="dossiers",
                extraction_method="fixture",
                confidence_score=0.9,
            )
        )
        session.commit()
    return factory


def test_bridge_derives_both_levels_is_idempotent_and_keeps_scores_insufficient(
    tmp_path,
):
    analytics_path = tmp_path / "analytics.db"
    _analytics_fixture(analytics_path)
    factory = _operational_factory(tmp_path / "operational.db")

    dry = import_analytics_indicators(
        analytics_path, dry_run=True, factory=factory
    )
    assert dry.inserted == 4
    with factory() as session:
        assert session.execute(
            select(InclusionObservation).where(
                InclusionObservation.extraction_method == BRIDGE_VERSION
            )
        ).scalars().all() == []

    first = import_analytics_indicators(analytics_path, factory=factory)
    second = import_analytics_indicators(analytics_path, factory=factory)
    assert first.inserted == 4
    assert second.inserted == 0
    assert second.unchanged == 4

    with factory() as session:
        rows = session.execute(
            select(InclusionObservation).where(
                InclusionObservation.extraction_method == BRIDGE_VERSION
            )
        ).scalars().all()
        values = {
            (row.geographic_level, row.geographic_code, row.indicator_code):
            row.value_numeric
            for row in rows
        }
        assert values[("department", "01", "taux_chomage")] == pytest.approx(10)
        assert values[("department", "03", "taux_chomage")] == pytest.approx(20)
        assert values[("region", "84", "taux_chomage")] == pytest.approx(
            250 / 1500 * 100
        )
        assert values[
            (
                "region",
                "84",
                "dossiers_surendettement_1000_habitants",
            )
        ] == pytest.approx(2)
        assert all("annual_source_year=2022" in row.source_fragment for row in rows)

        model = session.execute(
            select(RiskScoreModel).where(
                RiskScoreModel.code == "default",
                RiskScoreModel.version == "1.1.0",
            )
        ).scalar_one()
        mapped = {
            item.logical_code: item.indicator_id
            for item in session.execute(
                select(RiskScoreIndicatorConfig).where(
                    RiskScoreIndicatorConfig.risk_score_model_id == model.id
                )
            ).scalars()
        }
        assert mapped["taux_chomage"] is not None
        assert mapped["dossiers_surendettement_1000_habitants"] is not None
        assert mapped["taux_pauvrete"] is None

    region = RiskScoreCalculator(factory).calculate(
        "region", "2025-06", dry_run=True
    )
    department = RiskScoreCalculator(factory).calculate(
        "department", "2025-06", dry_run=True
    )
    assert region.results[0].coverage_ratio == pytest.approx(0.5)
    assert region.results[0].status == "insufficient_data"
    assert all(item.status == "insufficient_data" for item in department.results)
    assert all(item.coverage_ratio == pytest.approx(0.2) for item in department.results)
