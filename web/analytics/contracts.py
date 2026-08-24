"""Minimal runtime validation for responses returned by FastAPI."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class AnalyticsResponseError(ValueError):
    """Raised when the analytical API response violates its contract."""


def _mapping(value: Any, context: str) -> Mapping:
    if not isinstance(value, Mapping):
        raise AnalyticsResponseError(f"{context} must be an object")
    return value


def _list(value: Any, context: str) -> list:
    if not isinstance(value, list):
        raise AnalyticsResponseError(f"{context} must be a list")
    return value


def _required(item: Mapping, fields: tuple[str, ...], context: str) -> None:
    missing = [field for field in fields if field not in item]
    if missing:
        raise AnalyticsResponseError(
            f"{context} is missing fields: {', '.join(missing)}"
        )


def validate_models(payload: Any) -> list[dict]:
    models = _list(payload, "models")
    for index, model in enumerate(models):
        item = _mapping(model, f"models[{index}]")
        _required(
            item,
            ("code", "name", "version", "is_active", "indicators"),
            f"models[{index}]",
        )
        _list(item["indicators"], f"models[{index}].indicators")
    return models


def validate_score(item: Any, context: str = "score") -> dict:
    score = _mapping(item, context)
    _required(
        score,
        (
            "geographic_level",
            "geographic_code",
            "reference_period",
            "score",
            "coverage_ratio",
            "status",
            "model",
            "details",
        ),
        context,
    )
    _mapping(score["model"], f"{context}.model")
    _list(score["details"], f"{context}.details")
    if score["score"] is not None and not isinstance(score["score"], (int, float)):
        raise AnalyticsResponseError(f"{context}.score must be numeric or null")
    if not isinstance(score["coverage_ratio"], (int, float)):
        raise AnalyticsResponseError(f"{context}.coverage_ratio must be numeric")
    return dict(score)


def validate_scores(payload: Any) -> list[dict]:
    scores = _list(payload, "scores")
    return [
        validate_score(score, f"scores[{index}]")
        for index, score in enumerate(scores)
    ]


def validate_series(payload: Any) -> dict:
    series = _mapping(payload, "series response")
    _required(
        series,
        ("geographic_level", "geographic_code", "count", "series"),
        "series response",
    )
    result = dict(series)
    result["series"] = validate_scores(series["series"])
    return result


def validate_factors(payload: Any) -> dict:
    factors = _mapping(payload, "factors response")
    _required(
        factors,
        (
            "geographic_level",
            "geographic_code",
            "reference_period",
            "score",
            "coverage_ratio",
            "model",
            "factors",
        ),
        "factors response",
    )
    _list(factors["factors"], "factors response.factors")
    return dict(factors)


def validate_comparison(payload: Any) -> dict:
    comparison = _mapping(payload, "model comparison")
    _required(
        comparison,
        ("status", "version_a", "version_b"),
        "model comparison",
    )
    if comparison["status"] == "ok":
        _required(
            comparison,
            ("territory_periods_compared", "rows"),
            "model comparison",
        )
    return dict(comparison)


def validate_observability(payload: Any) -> dict:
    return dict(_mapping(payload, "observability response"))


def validate_territorial_rows(payload: Any) -> list[dict]:
    rows = _list(payload, "territorial data")
    return [dict(_mapping(row, f"territorial data[{index}]")) for index, row in enumerate(rows)]
