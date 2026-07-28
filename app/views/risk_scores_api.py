"""FastAPI routes for territorial risk scores and model versions."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.schemas.risk_scores import RiskScoreCalculateRequest
from src.risk_score.service import RiskScoreCalculator, normalize_geographic_level
from src.storage.database import get_session_factory
from src.storage.models import (
    RiskScore,
    RiskScoreDetail,
    RiskScoreIndicatorConfig,
    RiskScoreModel,
)

risk_scores_api = APIRouter(prefix="/api", tags=["Risk scores"])


@risk_scores_api.get("/risk-score-models")
def list_risk_score_models(active_only: bool = False) -> list[dict]:
    statement = select(RiskScoreModel).order_by(RiskScoreModel.code, RiskScoreModel.id.desc())
    if active_only:
        statement = statement.where(RiskScoreModel.is_active.is_(True))
    factory = get_session_factory()
    with factory() as session:
        models = session.execute(statement).scalars().all()
        output = []
        for model in models:
            configs = session.execute(
                select(RiskScoreIndicatorConfig).where(
                    RiskScoreIndicatorConfig.risk_score_model_id == model.id
                )
            ).scalars().all()
            output.append(
                {
                    "id": model.id,
                    "code": model.code,
                    "name": model.name,
                    "version": model.version,
                    "description": model.description,
                    "normalization_method": model.normalization_method,
                    "minimum_coverage_ratio": float(model.minimum_coverage_ratio),
                    "is_active": model.is_active,
                    "configuration": json.loads(model.configuration_json),
                    "indicators": [
                        {
                            "logical_code": config.logical_code,
                            "indicator_code": config.indicator_code,
                            "indicator_id": config.indicator_id,
                            "weight": float(config.weight),
                            "direction": config.direction,
                            "expected_unit": config.expected_unit,
                            "is_active": config.is_active,
                        }
                        for config in configs
                    ],
                }
            )
        return output


@risk_scores_api.get("/risk-scores")
def list_risk_scores(
    geographic_level: str | None = None,
    geographic_code: str | None = None,
    reference_period: str | None = None,
    model_code: str | None = None,
    risk_level: str | None = None,
    sort: str = Query("score_desc", pattern="^(score_asc|score_desc)$"),
    limit: int = Query(100, ge=1, le=5000),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    statement = select(RiskScore, RiskScoreModel).join(
        RiskScoreModel,
        RiskScoreModel.id == RiskScore.risk_score_model_id,
    )
    if geographic_level:
        statement = statement.where(
            RiskScore.geographic_level == _validated_level(geographic_level)
        )
    if geographic_code:
        statement = statement.where(RiskScore.geographic_code == geographic_code)
    if reference_period:
        statement = statement.where(RiskScore.reference_period == reference_period)
    if model_code:
        statement = statement.where(RiskScoreModel.code == model_code)
    if risk_level:
        statement = statement.where(RiskScore.risk_level == risk_level)
    order = RiskScore.score.asc().nullslast() if sort == "score_asc" else RiskScore.score.desc().nullslast()
    statement = statement.order_by(order, RiskScore.id).limit(limit).offset(offset)
    factory = get_session_factory()
    with factory() as session:
        return [
            _serialize_score(session, score, model, include_details=True)
            for score, model in session.execute(statement)
        ]


@risk_scores_api.get("/risk-scores/{geographic_level}/{geographic_code}")
def get_risk_scores_for_territory(
    geographic_level: str,
    geographic_code: str,
) -> list[dict]:
    rows = list_risk_scores(
        geographic_level=geographic_level,
        geographic_code=geographic_code,
        sort="score_desc",
        limit=5000,
        offset=0,
    )
    if not rows:
        raise HTTPException(
            status_code=404,
            detail={"code": "risk_scores_not_found", "message": "No scores found"},
        )
    return rows


@risk_scores_api.get(
    "/risk-scores/{geographic_level}/{geographic_code}/{reference_period}"
)
def get_risk_score(
    geographic_level: str,
    geographic_code: str,
    reference_period: str,
    model_code: str = "default",
) -> dict:
    rows = list_risk_scores(
        geographic_level=geographic_level,
        geographic_code=geographic_code,
        reference_period=reference_period,
        model_code=model_code,
        sort="score_desc",
        limit=1,
        offset=0,
    )
    if not rows:
        raise HTTPException(
            status_code=404,
            detail={"code": "risk_score_not_found", "message": "Risk score not found"},
        )
    return rows[0]


@risk_scores_api.post("/risk-scores/calculate")
def calculate_risk_scores(payload: RiskScoreCalculateRequest) -> dict:
    try:
        summary = RiskScoreCalculator().calculate(
            geographic_level=payload.geographic_level,
            reference_period=payload.reference_period,
            model_code=payload.model_code,
            geographic_code=payload.geographic_code,
            all_periods=payload.all_periods,
            dry_run=payload.dry_run,
        )
        result = summary.to_dict()
        result["results"] = [
            {
                **item,
                "details": [detail for detail in item["details"]],
            }
            for item in result["results"]
        ]
        return result
    except (LookupError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "risk_score_calculation_invalid", "message": str(exc)},
        ) from exc


def _serialize_score(
    session,
    score: RiskScore,
    model: RiskScoreModel,
    include_details: bool,
) -> dict:
    levels = json.loads(model.configuration_json).get("risk_levels", [])
    level_label = next(
        (item["label"] for item in levels if item["code"] == score.risk_level),
        None,
    )
    details = []
    if include_details:
        stored_details = session.execute(
            select(RiskScoreDetail)
            .where(RiskScoreDetail.risk_score_id == score.id)
            .order_by(RiskScoreDetail.contribution.desc())
        ).scalars()
        details = [
            {
                "indicator_code": detail.indicator_code,
                "raw_value": float(detail.raw_value),
                "unit": detail.unit,
                "population_min": float(detail.population_min),
                "population_max": float(detail.population_max),
                "normalized_value": float(detail.normalized_value),
                "configured_weight": float(detail.configured_weight),
                "effective_weight": float(detail.effective_weight),
                "contribution": float(detail.contribution),
                "direction": detail.direction,
                "source_observation_id": detail.source_observation_id,
            }
            for detail in stored_details
        ]
    return {
        "id": score.id,
        "geographic_level": score.geographic_level,
        "geographic_code": score.geographic_code,
        "geographic_name": score.geographic_name,
        "reference_period": score.reference_period,
        "score": float(score.score) if score.score is not None else None,
        "risk_level": {"code": score.risk_level, "label": level_label},
        "coverage_ratio": float(score.coverage_ratio),
        "status": score.status,
        "model": {"code": model.code, "version": model.version},
        "missing_indicators": json.loads(score.missing_indicators_json),
        "warnings": json.loads(score.warnings_json),
        "details": details,
    }


def _validated_level(value: str) -> str:
    try:
        return normalize_geographic_level(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_geographic_level", "message": str(exc)},
        ) from exc
