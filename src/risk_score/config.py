"""Versioned configuration and seed helpers for risk scoring."""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.storage.models import (
    InclusionIndicator,
    RiskScoreIndicatorConfig,
    RiskScoreModel,
)

DEFAULT_MODEL_SPEC: dict[str, Any] = {
    "code": "default",
    "name": "Score territorial de risque de surendettement",
    "version": "1.0.0",
    "description": (
        "Indice statistique territorial transparent. Il ne constitue ni une décision "
        "individuelle de crédit ni une mesure certaine du risque d'une personne."
    ),
    "normalization_method": "min_max",
    "minimum_coverage_ratio": 0.60,
    "risk_levels": [
        {"code": "very_low", "label": "Très faible", "min": 0.0, "max": 20.0},
        {"code": "low", "label": "Faible", "min": 20.0, "max": 40.0},
        {"code": "moderate", "label": "Modéré", "min": 40.0, "max": 60.0},
        {"code": "high", "label": "Élevé", "min": 60.0, "max": 80.0},
        {"code": "very_high", "label": "Très élevé", "min": 80.0, "max": 100.0000001},
    ],
    "indicators": [
        {
            "logical_code": "dossiers_surendettement_1000_habitants",
            "database_code": None,
            "weight": 0.30,
            "direction": "positive",
            "expected_unit": "dossiers_pour_1000_habitants",
        },
        {
            "logical_code": "taux_chomage",
            "database_code": None,
            "weight": 0.20,
            "direction": "positive",
            "expected_unit": "%",
        },
        {
            "logical_code": "taux_pauvrete",
            "database_code": None,
            "weight": 0.20,
            "direction": "positive",
            "expected_unit": "%",
        },
        {
            "logical_code": "revenu_median",
            "database_code": None,
            "weight": 0.15,
            "direction": "negative",
            "expected_unit": "euros",
        },
        {
            "logical_code": "endettement_moyen",
            "database_code": None,
            "weight": 0.10,
            "direction": "positive",
            "expected_unit": "euros",
        },
        {
            "logical_code": "inflation",
            "database_code": None,
            "weight": 0.05,
            "direction": "positive",
            "expected_unit": "%",
        },
    ],
}

MODEL_1_1_SPEC: dict[str, Any] = {
    **DEFAULT_MODEL_SPEC,
    "version": "1.1.0",
    "description": (
        f"{DEFAULT_MODEL_SPEC['description']} Version intégrant explicitement "
        "les indicateurs dérivés par la passerelle analytique v1."
    ),
    "indicators": [
        {
            **item,
            "database_code": (
                item["logical_code"]
                if item["logical_code"]
                in {
                    "dossiers_surendettement_1000_habitants",
                    "taux_chomage",
                    "taux_pauvrete",
                    "revenu_median",
                }
                else None
            ),
        }
        for item in DEFAULT_MODEL_SPEC["indicators"]
    ],
}

MODEL_1_2_SPEC: dict[str, Any] = {
    **MODEL_1_1_SPEC,
    "version": "1.2.0",
    "normalization_method": "winsorized_min_max",
    "description": (
        f"{DEFAULT_MODEL_SPEC['description']} Version robuste 1.2 : normalisation "
        "Min-Max bornée aux percentiles 5 et 95 de chaque cohorte territoriale."
    ),
    "normalization_parameters": {
        "lower_percentile": 0.05,
        "upper_percentile": 0.95,
        "reference_scope": "geographic_level_and_period",
    },
}


def seed_default_model(
    session: Session,
    mapping: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Create the default model once and report unresolved indicator mappings."""
    mapping = mapping or {}
    spec = DEFAULT_MODEL_SPEC
    existing = session.execute(
        select(RiskScoreModel).where(
            RiskScoreModel.code == spec["code"],
            RiskScoreModel.version == spec["version"],
        )
    ).scalar_one_or_none()
    if existing:
        _apply_mapping(session, existing, mapping)
        return _mapping_report(session, existing)

    configured_weight = sum(float(item["weight"]) for item in spec["indicators"])
    if abs(configured_weight - 1.0) > 1e-9:
        raise ValueError(f"Default model weights must sum to 1, got {configured_weight}")

    session.query(RiskScoreModel).filter(RiskScoreModel.code == spec["code"]).update(
        {"is_active": False}
    )
    model = RiskScoreModel(
        code=spec["code"],
        name=spec["name"],
        version=spec["version"],
        description=spec["description"],
        normalization_method=spec["normalization_method"],
        minimum_coverage_ratio=spec["minimum_coverage_ratio"],
        is_active=True,
        configuration_json=json.dumps(
            {"risk_levels": spec["risk_levels"]},
            ensure_ascii=False,
        ),
    )
    session.add(model)
    session.flush()

    indicators_by_code = {
        indicator.code: indicator
        for indicator in session.execute(select(InclusionIndicator)).scalars()
    }
    for item in spec["indicators"]:
        logical_code = item["logical_code"]
        database_code = mapping.get(logical_code) or item["database_code"] or logical_code
        indicator = indicators_by_code.get(database_code)
        session.add(
            RiskScoreIndicatorConfig(
                risk_score_model_id=model.id,
                indicator_id=indicator.id if indicator else None,
                indicator_code=database_code,
                logical_code=logical_code,
                weight=item["weight"],
                direction=item["direction"],
                normalization_method=spec["normalization_method"],
                expected_unit=item["expected_unit"],
                is_required=False,
                is_active=True,
            )
        )
    session.flush()
    return _mapping_report(session, model)


def seed_model_1_1(session: Session) -> dict[str, Any]:
    """Seed the bridge-aware model while leaving unavailable inputs unresolved."""
    return _seed_model(session, MODEL_1_1_SPEC)


def seed_model_1_2(session: Session) -> dict[str, Any]:
    """Seed the robust model without mutating the preceding model versions."""
    return _seed_model(session, MODEL_1_2_SPEC)


def _seed_model(session: Session, spec: dict[str, Any]) -> dict[str, Any]:
    existing = session.execute(
        select(RiskScoreModel).where(
            RiskScoreModel.code == spec["code"],
            RiskScoreModel.version == spec["version"],
        )
    ).scalar_one_or_none()
    if existing:
        session.query(RiskScoreModel).filter(
            RiskScoreModel.code == spec["code"]
        ).update({"is_active": False})
        existing.is_active = True
        indicators = {
            item.code: item
            for item in session.execute(select(InclusionIndicator)).scalars()
        }
        configurations = session.execute(
            select(RiskScoreIndicatorConfig).where(
                RiskScoreIndicatorConfig.risk_score_model_id == existing.id
            )
        ).scalars()
        mapped_codes = {
            item["logical_code"]: item["database_code"]
            for item in spec["indicators"]
            if item["database_code"]
        }
        for configuration in configurations:
            database_code = mapped_codes.get(configuration.logical_code)
            source = indicators.get(database_code) if database_code else None
            if source:
                configuration.indicator_id = source.id
                configuration.indicator_code = source.code
        session.flush()
        return _mapping_report(session, existing)
    session.query(RiskScoreModel).filter(
        RiskScoreModel.code == spec["code"]
    ).update({"is_active": False})
    model = RiskScoreModel(
        code=spec["code"],
        name=spec["name"],
        version=spec["version"],
        description=spec["description"],
        normalization_method=spec["normalization_method"],
        minimum_coverage_ratio=spec["minimum_coverage_ratio"],
        is_active=True,
        configuration_json=json.dumps(
            {
                "risk_levels": spec["risk_levels"],
                "normalization_parameters": spec.get(
                    "normalization_parameters", {}
                ),
            },
            ensure_ascii=False,
        ),
    )
    session.add(model)
    session.flush()
    indicators = {
        item.code: item
        for item in session.execute(select(InclusionIndicator)).scalars()
    }
    for item in spec["indicators"]:
        code = item["database_code"] or item["logical_code"]
        source = indicators.get(code) if item["database_code"] else None
        session.add(
            RiskScoreIndicatorConfig(
                risk_score_model_id=model.id,
                indicator_id=source.id if source else None,
                indicator_code=code,
                logical_code=item["logical_code"],
                weight=item["weight"],
                direction=item["direction"],
                normalization_method=spec["normalization_method"],
                expected_unit=item["expected_unit"],
                is_required=False,
                is_active=True,
            )
        )
    session.flush()
    return _mapping_report(session, model)


def _apply_mapping(
    session: Session,
    model: RiskScoreModel,
    mapping: dict[str, str],
) -> None:
    """Apply only explicit mappings and reject unknown source indicators."""
    if not mapping:
        return
    configurations = {
        config.logical_code: config
        for config in session.execute(
            select(RiskScoreIndicatorConfig).where(
                RiskScoreIndicatorConfig.risk_score_model_id == model.id
            )
        ).scalars()
    }
    for logical_code, database_code in mapping.items():
        if logical_code not in configurations:
            raise ValueError(f"Unknown logical indicator: {logical_code}")
        indicator = session.execute(
            select(InclusionIndicator).where(
                InclusionIndicator.code == database_code
            )
        ).scalar_one_or_none()
        if indicator is None:
            raise ValueError(
                f"Unknown source indicator for {logical_code}: {database_code}"
            )
        configuration = configurations[logical_code]
        configuration.indicator_id = indicator.id
        configuration.indicator_code = indicator.code
    session.flush()


def _mapping_report(session: Session, model: RiskScoreModel) -> dict[str, Any]:
    existing_codes = [
        row[0] for row in session.execute(select(InclusionIndicator.code)).all()
    ]
    configs = session.execute(
        select(RiskScoreIndicatorConfig).where(
            RiskScoreIndicatorConfig.risk_score_model_id == model.id
        )
    ).scalars()
    unresolved = []
    for config in configs:
        if config.indicator_id is None:
            unresolved.append(
                {
                    "logical_code": config.logical_code,
                    "configured_database_code": config.indicator_code,
                    "candidates": _mapping_candidates(
                        config.logical_code,
                        existing_codes,
                    ),
                }
            )
    return {
        "model_id": model.id,
        "code": model.code,
        "version": model.version,
        "created": model.created_at,
        "unresolved_mappings": unresolved,
    }


def _mapping_candidates(logical_code: str, existing_codes: list[str]) -> list[str]:
    ignored = {"taux", "part", "nombre", "moyen", "moyenne", "median", "mediane"}
    logical_tokens = _tokens(logical_code) - ignored
    ranked = []
    for code in existing_codes:
        overlap = logical_tokens & (_tokens(code) - ignored)
        if overlap:
            ranked.append((len(overlap), code))
    return [code for _, code in sorted(ranked, key=lambda item: (-item[0], item[1]))[:3]]


def _tokens(value: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", value.lower())
    ascii_value = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return {token for token in re.split(r"[^a-z0-9]+", ascii_value) if token}
