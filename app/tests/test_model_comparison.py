import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.risk_score.model_comparison import compare_model_versions
from src.storage.models import Base, RiskScore, RiskScoreModel


def test_compare_model_versions(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'comparison.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        models = []
        for version in ("1.1.0", "1.2.0"):
            model = RiskScoreModel(
                code="default",
                name="Test",
                version=version,
                normalization_method="min_max",
                minimum_coverage_ratio=0.6,
                is_active=version == "1.2.0",
                configuration_json=json.dumps({}),
            )
            session.add(model)
            models.append(model)
        session.flush()
        for model, scores in zip(models, ((20, 80), (25, 75))):
            for code, score in zip(("01", "02"), scores):
                session.add(
                    RiskScore(
                        risk_score_model_id=model.id,
                        geographic_level="department",
                        geographic_code=code,
                        geographic_name=code,
                        reference_period="2024",
                        score=score,
                        risk_level="low" if score < 40 else "high",
                        coverage_ratio=0.9,
                        status="partial",
                        missing_indicators_json="[]",
                        warnings_json="[]",
                    )
                )
        session.commit()
    monkeypatch.setattr(
        "src.risk_score.model_comparison.get_session_factory",
        lambda: factory,
    )
    report = compare_model_versions(reference_period="2024")
    assert report["territory_periods_compared"] == 2
    assert report["rank_spearman"] == pytest.approx(1.0)
    assert report["mean_absolute_score_delta"] == 5.0
