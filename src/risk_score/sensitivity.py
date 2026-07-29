"""Reference bounds and weight sensitivity for model governance."""

from __future__ import annotations

import pandas as pd
from sqlalchemy import select

from src.risk_score.service import percentile
from src.risk_score.service import min_max_normalize
from src.storage.database import get_session_factory
from src.storage.models import (
    InclusionObservation,
    RiskScoreIndicatorConfig,
    RiskScoreModel,
    RiskScore,
)

WEIGHT_SCENARIOS = {
    "baseline": {
        "dossiers_surendettement_1000_habitants": 0.30,
        "taux_chomage": 0.20,
        "taux_pauvrete": 0.20,
        "revenu_median": 0.15,
        "endettement_moyen": 0.10,
        "inflation": 0.05,
    },
    "equal_available": {
        "dossiers_surendettement_1000_habitants": 1 / 6,
        "taux_chomage": 1 / 6,
        "taux_pauvrete": 1 / 6,
        "revenu_median": 1 / 6,
        "endettement_moyen": 1 / 6,
        "inflation": 1 / 6,
    },
    "dossier_heavy": {
        "dossiers_surendettement_1000_habitants": 0.45,
        "taux_chomage": 0.15,
        "taux_pauvrete": 0.15,
        "revenu_median": 0.10,
        "endettement_moyen": 0.10,
        "inflation": 0.05,
    },
}


def build_reference_bounds(
    *,
    geographic_level: str = "department",
    periods: tuple[str, ...] = ("2023", "2024"),
    lower_quantile: float = 0.05,
    upper_quantile: float = 0.95,
) -> dict:
    factory = get_session_factory()
    with factory() as session:
        model = session.execute(
            select(RiskScoreModel).where(
                RiskScoreModel.code == "default",
                RiskScoreModel.is_active.is_(True),
            )
        ).scalar_one()
        configs = session.execute(
            select(RiskScoreIndicatorConfig).where(
                RiskScoreIndicatorConfig.risk_score_model_id == model.id,
                RiskScoreIndicatorConfig.indicator_id.is_not(None),
                RiskScoreIndicatorConfig.is_active.is_(True),
            )
        ).scalars()
        bounds = {}
        for config in configs:
            values = [
                float(value)
                for value in session.execute(
                    select(InclusionObservation.value_numeric).where(
                        InclusionObservation.geographic_level == geographic_level,
                        InclusionObservation.reference_period.in_(periods),
                        InclusionObservation.indicator_id == config.indicator_id,
                        InclusionObservation.unit == config.expected_unit,
                        InclusionObservation.value_numeric.is_not(None),
                    )
                ).scalars()
            ]
            if values:
                bounds[config.logical_code] = {
                    "fixed_min": percentile(values, lower_quantile),
                    "fixed_max": percentile(values, upper_quantile),
                    "observations": len(values),
                    "unit": config.expected_unit,
                }
    return {
        "status": "candidate_not_activated",
        "model_source_version": model.version,
        "geographic_level": geographic_level,
        "reference_periods": list(periods),
        "lower_quantile": lower_quantile,
        "upper_quantile": upper_quantile,
        "bounds": bounds,
    }


def validate_weight_scenarios(
    scenarios: dict[str, dict[str, float]] = WEIGHT_SCENARIOS,
) -> None:
    expected = set(WEIGHT_SCENARIOS["baseline"])
    for name, weights in scenarios.items():
        if set(weights) != expected:
            raise ValueError(f"Scenario {name} does not define all indicators")
        if any(value <= 0 for value in weights.values()):
            raise ValueError(f"Scenario {name} contains a non-positive weight")
        if abs(sum(weights.values()) - 1.0) > 1e-9:
            raise ValueError(f"Scenario {name} weights do not sum to 1")


def summarize_reference_bounds() -> pd.DataFrame:
    report = build_reference_bounds()
    return pd.DataFrame.from_dict(report["bounds"], orient="index")


def analyze_sensitivity(
    *,
    reference_period: str = "2024",
    geographic_level: str = "department",
) -> dict:
    validate_weight_scenarios()
    bounds_report = build_reference_bounds(geographic_level=geographic_level)
    bounds = bounds_report["bounds"]
    factory = get_session_factory()
    with factory() as session:
        model = session.execute(
            select(RiskScoreModel).where(
                RiskScoreModel.code == "default",
                RiskScoreModel.is_active.is_(True),
            )
        ).scalar_one()
        configs = {
            item.indicator_code: item
            for item in session.execute(
                select(RiskScoreIndicatorConfig).where(
                    RiskScoreIndicatorConfig.risk_score_model_id == model.id,
                    RiskScoreIndicatorConfig.indicator_id.is_not(None),
                )
            ).scalars()
        }
        observations = session.execute(
            select(InclusionObservation).where(
                InclusionObservation.geographic_level == geographic_level,
                InclusionObservation.reference_period == reference_period,
                InclusionObservation.indicator_code.in_(configs),
                InclusionObservation.value_numeric.is_not(None),
            )
        ).scalars().all()
        current_scores = {
            row.geographic_code: float(row.score)
            for row in session.execute(
                select(RiskScore).where(
                    RiskScore.risk_score_model_id == model.id,
                    RiskScore.geographic_level == geographic_level,
                    RiskScore.reference_period == reference_period,
                    RiskScore.score.is_not(None),
                )
            ).scalars()
        }
    values_by_territory: dict[str, dict[str, float]] = {}
    for observation in observations:
        values_by_territory.setdefault(
            str(observation.geographic_code), {}
        ).setdefault(
            observation.indicator_code, float(observation.value_numeric)
        )
    scenario_scores = {}
    for scenario_name, weights in WEIGHT_SCENARIOS.items():
        scenario_scores[scenario_name] = {
            code: _fixed_reference_score(values, configs, bounds, weights)
            for code, values in values_by_territory.items()
        }
    baseline = pd.Series(current_scores, name="current_1_2")
    comparisons = {}
    for name, scores in scenario_scores.items():
        candidate = pd.Series(scores, name=name)
        frame = pd.concat([baseline, candidate], axis=1).dropna()
        delta = frame[name] - frame["current_1_2"]
        comparisons[name] = {
            "territories": len(frame),
            "rank_spearman": float(
                frame["current_1_2"].rank().corr(frame[name].rank())
            ),
            "mean_absolute_delta": float(delta.abs().mean()),
            "maximum_absolute_delta": float(delta.abs().max()),
        }
    return {
        "status": "candidate_not_activated",
        "reference_period": reference_period,
        "geographic_level": geographic_level,
        "bounds": bounds,
        "scenarios": comparisons,
    }


def _fixed_reference_score(values, configs, bounds, weights):
    available = [
        code for code in values if code in configs and code in bounds
    ]
    total_weight = sum(weights[configs[code].logical_code] for code in available)
    if total_weight <= 0:
        return None
    score = 0.0
    for code in available:
        config = configs[code]
        logical_code = config.logical_code
        normalized = min_max_normalize(
            values[code],
            bounds[logical_code]["fixed_min"],
            bounds[logical_code]["fixed_max"],
            config.direction,
        )
        score += normalized * weights[logical_code] / total_weight * 100.0
    return score
