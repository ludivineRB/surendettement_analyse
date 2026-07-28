"""Testable business service for transparent territorial risk scores."""

from __future__ import annotations

import json
import math
import time
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Iterable

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from src.storage.database import get_session_factory
from src.storage.models import (
    InclusionObservation,
    InclusionSourceDocument,
    RiskScore,
    RiskScoreDetail,
    RiskScoreIndicatorConfig,
    RiskScoreModel,
)

GEOGRAPHIC_LEVEL_ALIASES = {
    "department": "department",
    "departement": "department",
    "département": "department",
    "dep": "department",
    "region": "region",
    "région": "region",
    "reg": "region",
}


@dataclass(slots=True)
class ObservationValue:
    id: int
    indicator_id: int | None
    indicator_code: str
    geographic_code: str
    geographic_name: str | None
    value: float
    unit: str | None


@dataclass(slots=True)
class ScoreDetailResult:
    indicator_id: int | None
    indicator_code: str
    raw_value: float
    unit: str | None
    population_min: float
    population_max: float
    normalized_value: float
    configured_weight: float
    effective_weight: float
    contribution: float
    direction: str
    source_observation_id: int


@dataclass(slots=True)
class TerritoryScoreResult:
    geographic_level: str
    geographic_code: str
    geographic_name: str | None
    reference_period: str
    score: float | None
    risk_level: str | None
    risk_level_label: str | None
    coverage_ratio: float
    status: str
    missing_indicators: list[str]
    warnings: list[str]
    details: list[ScoreDetailResult] = field(default_factory=list)


@dataclass(slots=True)
class ExecutionSummary:
    model_code: str
    model_version: str
    geographic_level: str
    periods: list[str]
    territories_analyzed: int = 0
    valid: int = 0
    partial: int = 0
    insufficient_data: int = 0
    errors: int = 0
    missing_indicators: set[str] = field(default_factory=set)
    incompatible_units: list[str] = field(default_factory=list)
    error_messages: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    results: list[TerritoryScoreResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["missing_indicators"] = sorted(self.missing_indicators)
        return payload


def normalize_geographic_level(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.strip().lower())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    try:
        return GEOGRAPHIC_LEVEL_ALIASES[normalized]
    except KeyError as exc:
        raise ValueError(f"Unsupported geographic level: {value}") from exc


def min_max_normalize(
    value: float,
    population_min: float,
    population_max: float,
    direction: str,
) -> float:
    if not all(math.isfinite(item) for item in (value, population_min, population_max)):
        raise ValueError("Normalization values must be finite")
    if direction not in {"positive", "negative"}:
        raise ValueError(f"Unsupported direction: {direction}")
    if population_min == population_max:
        normalized = 0.5
    else:
        normalized = (value - population_min) / (population_max - population_min)
    normalized = min(1.0, max(0.0, normalized))
    return 1.0 - normalized if direction == "negative" else normalized


def classify_risk(score: float, levels: Iterable[dict]) -> tuple[str, str]:
    bounded = min(100.0, max(0.0, score))
    for level in levels:
        if float(level["min"]) <= bounded < float(level["max"]):
            return str(level["code"]), str(level["label"])
    raise ValueError(f"No risk level configured for score={bounded}")


class RiskScoreCalculator:
    """Calculate and optionally persist reproducible territorial scores."""

    def __init__(self, factory: sessionmaker | None = None):
        self.factory = factory or get_session_factory()

    def calculate(
        self,
        geographic_level: str,
        reference_period: str | None = None,
        model_code: str = "default",
        geographic_code: str | None = None,
        all_periods: bool = False,
        dry_run: bool = False,
    ) -> ExecutionSummary:
        started = time.monotonic()
        level = normalize_geographic_level(geographic_level)
        with self.factory() as session:
            model = self._load_model(session, model_code)
            configs = self._load_configs(session, model.id)
            periods = self._resolve_periods(
                session,
                level,
                reference_period,
                all_periods,
            )
            summary = ExecutionSummary(
                model_code=model.code,
                model_version=model.version,
                geographic_level=level,
                periods=periods,
            )
            for period in periods:
                period_results = self._calculate_period(
                    session,
                    model,
                    configs,
                    level,
                    period,
                    geographic_code,
                    summary,
                )
                summary.results.extend(period_results)
                if not dry_run:
                    for result in period_results:
                        self._upsert_result(session, model.id, result)
            if not dry_run:
                session.commit()
        self._finalize_summary(summary)
        summary.duration_seconds = time.monotonic() - started
        return summary

    def explain(self, risk_score_id: int) -> str:
        with self.factory() as session:
            score = session.get(RiskScore, risk_score_id)
            if score is None:
                raise LookupError(f"Risk score not found: {risk_score_id}")
            model = session.get(RiskScoreModel, score.risk_score_model_id)
            details = session.execute(
                select(RiskScoreDetail)
                .where(RiskScoreDetail.risk_score_id == score.id)
                .order_by(RiskScoreDetail.contribution.desc())
            ).scalars().all()
            levels = json.loads(model.configuration_json).get("risk_levels", [])
            label = next(
                (item["label"] for item in levels if item["code"] == score.risk_level),
                score.risk_level or "indéterminé",
            )
            lines = [
                f"Le territoire {score.geographic_name or score.geographic_code} obtient "
                f"un score de risque de {float(score.score):.1f} sur 100, "
                f"correspondant à un niveau de risque {str(label).lower()}.",
                "",
                "Les principales contributions au score sont :",
            ]
            lines.extend(
                f"- {detail.indicator_code} : {float(detail.contribution):.1f} points ;"
                for detail in details[:5]
            )
            lines.extend(
                [
                    "",
                    f"La couverture du modèle est de {float(score.coverage_ratio) * 100:.0f} %.",
                ]
            )
            missing = json.loads(score.missing_indicators_json)
            if missing:
                lines.append(f"Indicateurs absents : {', '.join(missing)}.")
            return "\n".join(lines)

    @staticmethod
    def _load_model(session: Session, code: str) -> RiskScoreModel:
        model = session.execute(
            select(RiskScoreModel)
            .where(RiskScoreModel.code == code, RiskScoreModel.is_active.is_(True))
            .order_by(RiskScoreModel.id.desc())
        ).scalars().first()
        if model is None:
            raise LookupError(f"No active risk score model found for code={code}")
        return model

    @staticmethod
    def _load_configs(session: Session, model_id: int) -> list[RiskScoreIndicatorConfig]:
        configs = session.execute(
            select(RiskScoreIndicatorConfig).where(
                RiskScoreIndicatorConfig.risk_score_model_id == model_id,
                RiskScoreIndicatorConfig.is_active.is_(True),
            )
        ).scalars().all()
        if not configs:
            raise ValueError("The active risk score model has no active indicators")
        if any(float(config.weight) <= 0 for config in configs):
            raise ValueError("All active indicator weights must be strictly positive")
        return configs

    @staticmethod
    def _resolve_periods(
        session: Session,
        level: str,
        reference_period: str | None,
        all_periods: bool,
    ) -> list[str]:
        if all_periods:
            return list(
                session.execute(
                    select(InclusionObservation.reference_period)
                    .where(InclusionObservation.geographic_level == level)
                    .distinct()
                    .order_by(InclusionObservation.reference_period)
                ).scalars()
            )
        if not reference_period:
            raise ValueError("reference_period is required unless all_periods=True")
        return [reference_period]

    def _calculate_period(
        self,
        session: Session,
        model: RiskScoreModel,
        configs: list[RiskScoreIndicatorConfig],
        level: str,
        period: str,
        geographic_code: str | None,
        summary: ExecutionSummary,
    ) -> list[TerritoryScoreResult]:
        configs_by_code = {config.indicator_code: config for config in configs}
        statement = (
            select(InclusionObservation, InclusionSourceDocument)
            .join(
                InclusionSourceDocument,
                InclusionSourceDocument.id == InclusionObservation.source_document_id,
            )
            .where(
                InclusionObservation.geographic_level == level,
                InclusionObservation.reference_period == period,
                InclusionObservation.indicator_code.in_(configs_by_code),
                InclusionObservation.value_numeric.is_not(None),
                InclusionObservation.geographic_code.is_not(None),
            )
            .order_by(
                InclusionObservation.confidence_score.desc().nullslast(),
                InclusionSourceDocument.updated_date.desc().nullslast(),
                InclusionObservation.created_at.desc(),
                InclusionObservation.id.desc(),
            )
        )
        if geographic_code:
            statement = statement.where(
                InclusionObservation.geographic_code == str(geographic_code)
            )
        selected: dict[tuple[str, str], ObservationValue] = {}
        warnings_by_territory: dict[str, list[str]] = {}
        for observation, _document in session.execute(statement):
            code = str(observation.geographic_code)
            config = configs_by_code[observation.indicator_code]
            if not math.isfinite(float(observation.value_numeric)):
                warnings_by_territory.setdefault(code, []).append(
                    f"non_finite_value:{observation.indicator_code}"
                )
                continue
            if config.expected_unit and observation.unit != config.expected_unit:
                warning = (
                    f"incompatible_unit:{observation.indicator_code}:"
                    f"expected={config.expected_unit}:actual={observation.unit}"
                )
                warnings_by_territory.setdefault(code, []).append(warning)
                summary.incompatible_units.append(f"{code}:{warning}")
                continue
            selected.setdefault(
                (code, observation.indicator_code),
                ObservationValue(
                    id=observation.id,
                    indicator_id=observation.indicator_id,
                    indicator_code=observation.indicator_code,
                    geographic_code=code,
                    geographic_name=observation.geographic_name,
                    value=float(observation.value_numeric),
                    unit=observation.unit,
                ),
            )

        by_indicator: dict[str, list[float]] = {}
        by_territory: dict[str, dict[str, ObservationValue]] = {}
        for (territory_code, indicator_code), observation in selected.items():
            by_indicator.setdefault(indicator_code, []).append(observation.value)
            by_territory.setdefault(territory_code, {})[indicator_code] = observation
        territory_names = self._territory_universe(
            session,
            level,
            period,
            geographic_code,
        )
        for territory_code, observations in by_territory.items():
            territory_names.setdefault(
                territory_code,
                next(
                    (item.geographic_name for item in observations.values()),
                    None,
                ),
            )

        bounds = {
            code: (min(values), max(values))
            for code, values in by_indicator.items()
        }
        results = []
        for territory_code, territory_name in sorted(territory_names.items()):
            observations = by_territory.get(territory_code, {})
            try:
                results.append(
                    self._score_territory(
                        model,
                        configs,
                        territory_code,
                        territory_name,
                        observations,
                        bounds,
                        level,
                        period,
                        warnings_by_territory.get(territory_code, []),
                    )
                )
            except Exception as exc:
                summary.error_messages.append(f"{territory_code}:{period}:{exc}")
                results.append(
                    TerritoryScoreResult(
                        geographic_level=level,
                        geographic_code=territory_code,
                        geographic_name=next(
                            (item.geographic_name for item in observations.values()),
                            None,
                        ),
                        reference_period=period,
                        score=None,
                        risk_level=None,
                        risk_level_label=None,
                        coverage_ratio=0.0,
                        status="error",
                        missing_indicators=[],
                        warnings=[str(exc)],
                    )
                )
        return results

    @staticmethod
    def _territory_universe(
        session: Session,
        level: str,
        period: str,
        geographic_code: str | None,
    ) -> dict[str, str | None]:
        statement = (
            select(
                InclusionObservation.geographic_code,
                InclusionObservation.geographic_name,
            )
            .where(
                InclusionObservation.geographic_level == level,
                InclusionObservation.reference_period == period,
                InclusionObservation.geographic_code.is_not(None),
            )
            .distinct()
        )
        if geographic_code:
            statement = statement.where(
                InclusionObservation.geographic_code == str(geographic_code)
            )
        return {
            str(code): name
            for code, name in session.execute(statement)
            if code is not None
        }

    @staticmethod
    def _score_territory(
        model: RiskScoreModel,
        configs: list[RiskScoreIndicatorConfig],
        territory_code: str,
        territory_name: str | None,
        observations: dict[str, ObservationValue],
        bounds: dict[str, tuple[float, float]],
        level: str,
        period: str,
        warnings: list[str],
    ) -> TerritoryScoreResult:
        total_weight = sum(float(config.weight) for config in configs)
        available = [config for config in configs if config.indicator_code in observations]
        available_weight = sum(float(config.weight) for config in available)
        coverage = available_weight / total_weight if total_weight else 0.0
        missing = [
            config.logical_code
            for config in configs
            if config.indicator_code not in observations
        ]
        minimum_coverage = float(model.minimum_coverage_ratio)
        if coverage < minimum_coverage:
            return TerritoryScoreResult(
                geographic_level=level,
                geographic_code=territory_code,
                geographic_name=territory_name,
                reference_period=period,
                score=None,
                risk_level=None,
                risk_level_label=None,
                coverage_ratio=coverage,
                status="insufficient_data",
                missing_indicators=missing,
                warnings=warnings,
            )

        details = []
        for config in available:
            observation = observations[config.indicator_code]
            observed_min, observed_max = bounds[config.indicator_code]
            population_min = (
                float(config.fixed_min) if config.fixed_min is not None else observed_min
            )
            population_max = (
                float(config.fixed_max) if config.fixed_max is not None else observed_max
            )
            normalized = min_max_normalize(
                observation.value,
                population_min,
                population_max,
                config.direction,
            )
            effective_weight = float(config.weight) / available_weight
            contribution = normalized * effective_weight * 100.0
            details.append(
                ScoreDetailResult(
                    indicator_id=observation.indicator_id,
                    indicator_code=config.indicator_code,
                    raw_value=observation.value,
                    unit=observation.unit,
                    population_min=population_min,
                    population_max=population_max,
                    normalized_value=normalized,
                    configured_weight=float(config.weight),
                    effective_weight=effective_weight,
                    contribution=contribution,
                    direction=config.direction,
                    source_observation_id=observation.id,
                )
            )
        score = min(100.0, max(0.0, sum(item.contribution for item in details)))
        levels = json.loads(model.configuration_json).get("risk_levels", [])
        risk_level, risk_level_label = classify_risk(score, levels)
        return TerritoryScoreResult(
            geographic_level=level,
            geographic_code=territory_code,
            geographic_name=territory_name,
            reference_period=period,
            score=score,
            risk_level=risk_level,
            risk_level_label=risk_level_label,
            coverage_ratio=coverage,
            status="valid" if coverage >= 1.0 - 1e-12 else "partial",
            missing_indicators=missing,
            warnings=warnings,
            details=details,
        )

    @staticmethod
    def _upsert_result(
        session: Session,
        model_id: int,
        result: TerritoryScoreResult,
    ) -> RiskScore:
        score = session.execute(
            select(RiskScore).where(
                RiskScore.risk_score_model_id == model_id,
                RiskScore.geographic_level == result.geographic_level,
                RiskScore.geographic_code == result.geographic_code,
                RiskScore.reference_period == result.reference_period,
            )
        ).scalar_one_or_none()
        if score is None:
            score = RiskScore(
                risk_score_model_id=model_id,
                geographic_level=result.geographic_level,
                geographic_code=result.geographic_code,
                reference_period=result.reference_period,
                coverage_ratio=result.coverage_ratio,
                status=result.status,
            )
            session.add(score)
            session.flush()
        score.geographic_name = result.geographic_name
        score.score = result.score
        score.risk_level = result.risk_level
        score.coverage_ratio = result.coverage_ratio
        score.status = result.status
        score.missing_indicators_json = json.dumps(
            result.missing_indicators,
            ensure_ascii=False,
        )
        score.warnings_json = json.dumps(result.warnings, ensure_ascii=False)
        session.execute(
            delete(RiskScoreDetail).where(RiskScoreDetail.risk_score_id == score.id)
        )
        for detail in result.details:
            session.add(RiskScoreDetail(risk_score_id=score.id, **asdict(detail)))
        return score

    @staticmethod
    def _finalize_summary(summary: ExecutionSummary) -> None:
        summary.territories_analyzed = len(summary.results)
        for result in summary.results:
            summary.missing_indicators.update(result.missing_indicators)
            if result.status == "valid":
                summary.valid += 1
            elif result.status == "partial":
                summary.partial += 1
            elif result.status == "insufficient_data":
                summary.insufficient_data += 1
            else:
                summary.errors += 1
