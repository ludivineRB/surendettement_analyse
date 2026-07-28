import json
import math

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.views.risk_scores_api import (
    get_risk_score,
    list_risk_score_models,
    list_risk_scores,
)
from src.risk_score.legacy_import import import_legacy_surendettement
from src.risk_score.service import (
    RiskScoreCalculator,
    classify_risk,
    min_max_normalize,
    normalize_geographic_level,
)
from src.storage.models import (
    Base,
    InclusionIndicator,
    InclusionObservation,
    InclusionSourceDocument,
    RiskScore,
    RiskScoreDetail,
    RiskScoreIndicatorConfig,
    RiskScoreModel,
    SurendettementData,
)

RISK_LEVELS = [
    {"code": "very_low", "label": "Très faible", "min": 0, "max": 20},
    {"code": "low", "label": "Faible", "min": 20, "max": 40},
    {"code": "moderate", "label": "Modéré", "min": 40, "max": 60},
    {"code": "high", "label": "Élevé", "min": 60, "max": 80},
    {"code": "very_high", "label": "Très élevé", "min": 80, "max": 100.0000001},
]


@pytest.fixture()
def risk_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'risk.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        indicators = {}
        for code, unit in (("risk_a", "%"), ("risk_b", "euros"), ("risk_c", "count")):
            indicator = InclusionIndicator(
                code=code,
                label=code,
                category="test",
                default_unit=unit,
            )
            session.add(indicator)
            indicators[code] = indicator
        session.flush()
        model = RiskScoreModel(
            code="test",
            name="Test model",
            version="1.0.0",
            normalization_method="min_max",
            minimum_coverage_ratio=0.6,
            is_active=True,
            configuration_json=json.dumps({"risk_levels": RISK_LEVELS}),
        )
        session.add(model)
        session.flush()
        for code, weight, direction, unit in (
            ("risk_a", 0.5, "positive", "%"),
            ("risk_b", 0.3, "negative", "euros"),
            ("risk_c", 0.2, "positive", "count"),
        ):
            session.add(
                RiskScoreIndicatorConfig(
                    risk_score_model_id=model.id,
                    indicator_id=indicators[code].id,
                    indicator_code=code,
                    logical_code=code,
                    weight=weight,
                    direction=direction,
                    expected_unit=unit,
                    normalization_method="min_max",
                    is_active=True,
                )
            )
        session.flush()

        documents = []
        for index, updated in enumerate(("2025-01-01", "2025-02-01"), start=1):
            document = InclusionSourceDocument(
                source_name="Fixture",
                publication_type="test",
                region_code="fixture",
                region_name="Fixture",
                reference_period="2025",
                page_url=f"https://example.test/{index}",
                pdf_url=f"https://example.test/{index}.pdf",
                pdf_filename=f"{index}.pdf",
                pdf_sha256=str(index) * 64,
                storage_path=f"{index}.pdf",
                updated_date=updated,
                extraction_status="success",
                extractor_version="test",
            )
            session.add(document)
            documents.append(document)
        session.flush()

        rows = [
            ("department", "59", "Nord", "2025", "risk_a", 10, "%", 0.8, 0),
            ("department", "59", "Nord", "2025", "risk_a", 99, "%", 0.2, 1),
            ("department", "59", "Nord", "2025", "risk_b", 1000, "euros", 0.8, 0),
            ("department", "59", "Nord", "2025", "risk_c", 8, "count", 0.8, 0),
            ("department", "2A", "Corse-du-Sud", "2025", "risk_a", 20, "%", 0.8, 0),
            ("department", "2A", "Corse-du-Sud", "2025", "risk_b", 2000, "euros", 0.8, 0),
            ("department", "2B", "Haute-Corse", "2025", "risk_c", 4, "count", 0.8, 0),
            ("region", "32", "Hauts-de-France", "2025", "risk_a", 15, "%", 0.8, 0),
            ("region", "94", "Corse", "2025", "risk_a", 25, "%", 0.8, 0),
            ("department", "59", "Nord", "2024", "risk_a", 5, "%", 0.8, 0),
            ("department", "59", "Nord", "2025", "risk_b", 9999, "dollars", 0.9, 1),
        ]
        for number, row in enumerate(rows, start=1):
            level, geo_code, geo_name, period, code, value, unit, confidence, doc_index = row
            session.add(
                InclusionObservation(
                    source_document_id=documents[doc_index].id,
                    indicator_id=indicators[code].id,
                    idempotence_key=f"{number:064d}",
                    indicator_code=code,
                    region_code=geo_code if level == "region" else "",
                    reference_period=period,
                    geographic_level=level,
                    geographic_code=geo_code,
                    geographic_name=geo_name,
                    value_numeric=value,
                    unit=unit,
                    extraction_method="fixture",
                    confidence_score=confidence,
                )
            )
        session.commit()
    return factory


def test_normalization_and_classification():
    assert min_max_normalize(15, 10, 20, "positive") == 0.5
    assert min_max_normalize(15, 10, 20, "negative") == 0.5
    assert min_max_normalize(10, 10, 10, "positive") == 0.5
    assert min_max_normalize(-100, 0, 10, "positive") == 0
    assert min_max_normalize(100, 0, 10, "positive") == 1
    assert classify_risk(0, RISK_LEVELS)[0] == "very_low"
    assert classify_risk(70, RISK_LEVELS)[0] == "high"
    assert classify_risk(100, RISK_LEVELS)[0] == "very_high"
    with pytest.raises(ValueError):
        min_max_normalize(math.inf, 0, 1, "positive")


def test_calculation_missing_weights_levels_units_and_geographies(risk_factory):
    summary = RiskScoreCalculator(risk_factory).calculate(
        "département",
        "2025",
        model_code="test",
        dry_run=True,
    )
    results = {result.geographic_code: result for result in summary.results}

    assert set(results) == {"59", "2A", "2B"}
    assert results["59"].status == "valid"
    assert results["2A"].status == "partial"
    assert results["2A"].coverage_ratio == pytest.approx(0.8)
    assert sum(detail.effective_weight for detail in results["2A"].details) == pytest.approx(1)
    assert results["2B"].status == "insufficient_data"
    assert results["2B"].score is None
    assert 0 <= results["59"].score <= 100
    assert sum(detail.contribution for detail in results["59"].details) == pytest.approx(
        results["59"].score
    )
    selected_a = next(detail for detail in results["59"].details if detail.indicator_code == "risk_a")
    assert selected_a.raw_value == 10
    assert any("incompatible_unit:risk_b" in warning for warning in results["59"].warnings)

    region_summary = RiskScoreCalculator(risk_factory).calculate(
        "REG",
        "2025",
        model_code="test",
        dry_run=True,
    )
    assert {result.geographic_code for result in region_summary.results} == {"32", "94"}
    assert normalize_geographic_level("DEP") == "department"
    assert normalize_geographic_level("région") == "region"


def test_persistence_upsert_detail_replacement_and_all_periods(risk_factory):
    calculator = RiskScoreCalculator(risk_factory)
    first = calculator.calculate("department", "2025", model_code="test")
    second = calculator.calculate("department", "2025", model_code="test")
    assert first.territories_analyzed == second.territories_analyzed

    with risk_factory() as session:
        assert session.scalar(select(func.count()).select_from(RiskScore)) == 3
        before_details = session.scalar(select(func.count()).select_from(RiskScoreDetail))
    calculator.calculate("department", "2025", model_code="test")
    with risk_factory() as session:
        assert session.scalar(select(func.count()).select_from(RiskScore)) == 3
        assert session.scalar(select(func.count()).select_from(RiskScoreDetail)) == before_details

    dry = calculator.calculate(
        "department",
        model_code="test",
        all_periods=True,
        dry_run=True,
    )
    assert dry.periods == ["2024", "2025"]


def test_api_serialization(risk_factory, monkeypatch):
    RiskScoreCalculator(risk_factory).calculate("department", "2025", model_code="test")
    monkeypatch.setattr("app.views.risk_scores_api.get_session_factory", lambda: risk_factory)

    models = list_risk_score_models(active_only=True)
    assert models[0]["code"] == "test"
    scores = list_risk_scores(
        geographic_level="department",
        model_code="test",
        sort="score_desc",
        limit=100,
        offset=0,
    )
    assert scores
    assert "details" in scores[0]
    nord = get_risk_score("department", "59", "2025", model_code="test")
    assert nord["model"]["version"] == "1.0.0"


def test_legacy_import_is_idempotent_and_supports_corsica(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        session.add_all(
            [
                SurendettementData(
                    year=2024,
                    region="2A",
                    indicator="Dossiers",
                    value=12,
                    source_file="legacy.csv",
                ),
                SurendettementData(
                    year=2024,
                    region="Nom sans code",
                    indicator="Dossiers",
                    value=13,
                    source_file="legacy.csv",
                ),
            ]
        )
        session.commit()

    first = import_legacy_surendettement(factory)
    second = import_legacy_surendettement(factory)
    assert first.imported == 1
    assert len(first.non_importable) == 1
    assert second.imported == 0
    assert second.duplicates == 1
