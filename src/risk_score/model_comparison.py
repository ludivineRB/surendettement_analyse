"""Reproducible comparison of two persisted risk-score model versions."""

from __future__ import annotations

import pandas as pd
from sqlalchemy import select

from src.storage.database import get_session_factory
from src.storage.models import RiskScore, RiskScoreModel


def compare_model_versions(
    *,
    version_a: str = "1.1.0",
    version_b: str = "1.2.0",
    geographic_level: str = "department",
    reference_period: str | None = None,
) -> dict:
    factory = get_session_factory()
    with factory() as session:
        models = {
            model.version: model
            for model in session.execute(
                select(RiskScoreModel).where(
                    RiskScoreModel.code == "default",
                    RiskScoreModel.version.in_((version_a, version_b)),
                )
            ).scalars()
        }
        missing = sorted({version_a, version_b}.difference(models))
        if missing:
            raise LookupError(f"Unknown model versions: {missing}")
        frames = {}
        for version in (version_a, version_b):
            statement = select(RiskScore).where(
                RiskScore.risk_score_model_id == models[version].id,
                RiskScore.geographic_level == geographic_level,
                RiskScore.score.is_not(None),
            )
            if reference_period:
                statement = statement.where(
                    RiskScore.reference_period == reference_period
                )
            rows = session.execute(statement).scalars()
            frames[version] = pd.DataFrame(
                {
                    "geographic_code": row.geographic_code,
                    "geographic_name": row.geographic_name,
                    "reference_period": row.reference_period,
                    "score": float(row.score),
                    "risk_level": row.risk_level,
                    "coverage_ratio": float(row.coverage_ratio),
                }
                for row in rows
            )
    left, right = frames[version_a], frames[version_b]
    keys = ["geographic_code", "geographic_name", "reference_period"]
    if left.empty or right.empty:
        return {
            "status": "insufficient_data",
            "version_a": version_a,
            "version_b": version_b,
            "rows": [],
        }
    comparison = left.merge(
        right,
        on=keys,
        suffixes=("_a", "_b"),
        validate="one_to_one",
    )
    comparison["score_delta"] = comparison["score_b"] - comparison["score_a"]
    comparison["absolute_delta"] = comparison["score_delta"].abs()
    comparison["rank_a"] = comparison.groupby("reference_period")["score_a"].rank(
        method="average", ascending=False
    )
    comparison["rank_b"] = comparison.groupby("reference_period")["score_b"].rank(
        method="average", ascending=False
    )
    comparison["rank_delta"] = comparison["rank_b"] - comparison["rank_a"]
    comparison["risk_level_changed"] = (
        comparison["risk_level_a"] != comparison["risk_level_b"]
    )
    rank_correlation = comparison["rank_a"].corr(comparison["rank_b"])
    ordered = comparison.sort_values(
        ["reference_period", "absolute_delta"], ascending=[True, False]
    )
    return {
        "status": "ok",
        "version_a": version_a,
        "version_b": version_b,
        "geographic_level": geographic_level,
        "reference_period": reference_period,
        "territory_periods_compared": len(comparison),
        "rank_spearman": _optional_float(rank_correlation),
        "mean_absolute_score_delta": float(comparison["absolute_delta"].mean()),
        "maximum_absolute_score_delta": float(comparison["absolute_delta"].max()),
        "risk_level_changes": int(comparison["risk_level_changed"].sum()),
        "rows": ordered.to_dict(orient="records"),
        "interpretation": (
            "La version 1.2.0 conserve les indicateurs et pondérations de la "
            "version 1.1.0 ; seule la normalisation robuste aux valeurs extrêmes change."
        ),
    }


def _optional_float(value) -> float | None:
    return None if pd.isna(value) else float(value)
