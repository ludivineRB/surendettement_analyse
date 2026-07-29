"""Read-only business validation metrics for the active territorial score."""

from __future__ import annotations

import pandas as pd
from sqlalchemy import select

from src.storage.database import get_session_factory
from src.storage.models import RiskScore, RiskScoreDetail, RiskScoreModel


def build_score_validation_report(level: str = "region") -> dict:
    factory = get_session_factory()
    with factory() as session:
        model = session.execute(
            select(RiskScoreModel).where(
                RiskScoreModel.code == "default",
                RiskScoreModel.is_active.is_(True),
            )
        ).scalar_one()
        scores = session.execute(
            select(RiskScore).where(
                RiskScore.risk_score_model_id == model.id,
                RiskScore.geographic_level == level,
                RiskScore.score.is_not(None),
            )
        ).scalars().all()
        details = session.execute(
            select(RiskScoreDetail).join(
                RiskScore, RiskScore.id == RiskScoreDetail.risk_score_id
            ).where(
                RiskScore.risk_score_model_id == model.id,
                RiskScore.geographic_level == level,
            )
        ).scalars().all()

    frame = pd.DataFrame(
        {
            "score_id": row.id,
            "code": row.geographic_code,
            "name": row.geographic_name,
            "period": row.reference_period,
            "score": float(row.score),
        }
        for row in scores
    )
    detail_frame = pd.DataFrame(
        {
            "score_id": row.risk_score_id,
            "indicator": row.indicator_code,
            "raw_value": float(row.raw_value),
            "normalized": float(row.normalized_value),
        }
        for row in details
    )
    if frame.empty:
        return {"model_version": model.version, "status": "insufficient_data"}

    dossier = detail_frame[
        detail_frame["indicator"] == "dossiers_surendettement_1000_habitants"
    ][["score_id", "raw_value"]]
    joined = frame.merge(dossier, on="score_id", how="inner")
    dossier_correlation = (
        _spearman(joined["score"], joined["raw_value"])
        if len(joined) >= 3
        else None
    )

    ordered = frame.sort_values(["code", "period"])
    ordered["monthly_change"] = ordered.groupby("code")["score"].diff()
    volatility = (
        ordered.groupby(["code", "name"], dropna=False)["monthly_change"]
        .apply(lambda values: values.abs().mean())
        .dropna()
        .sort_values(ascending=False)
    )

    equal_weight = (
        detail_frame.groupby("score_id")["normalized"].mean().mul(100).rename("equal_score")
    )
    sensitivity = frame.join(equal_weight, on="score_id")
    weight_correlation = (
        _spearman(sensitivity["score"], sensitivity["equal_score"])
        if len(sensitivity.dropna(subset=["equal_score"])) >= 3
        else None
    )
    return {
        "model_version": model.version,
        "status": "ok",
        "scores_analyzed": len(frame),
        "dossier_rate_spearman": _optional_float(dossier_correlation),
        "mean_absolute_monthly_change": _optional_float(
            ordered["monthly_change"].abs().mean()
        ),
        "equal_weight_rank_spearman": _optional_float(weight_correlation),
        "most_volatile": [
            {"geographic_code": code, "geographic_name": name, "mean_abs_change": float(value)}
            for (code, name), value in volatility.head(10).items()
        ],
        "limitations": [
            "Indice territorial comparatif, sans interprétation causale ou individuelle.",
            "Les variables annuelles sont répétées sur les mois de leur année source.",
            "L’inflation nationale informe le temps mais ne discrimine pas les territoires.",
            "La normalisation reste relative à la cohorte du niveau et de la période.",
        ],
    }


def _optional_float(value) -> float | None:
    return None if pd.isna(value) else float(value)


def _spearman(left: pd.Series, right: pd.Series) -> float:
    """Compute Spearman as Pearson correlation of ranks, without SciPy."""
    return float(left.rank(method="average").corr(right.rank(method="average")))
