"""Execution of validated analytical intents through allow-listed API calls."""

from __future__ import annotations

from dataclasses import dataclass

from assistant_api.analytical_intents import AnalyticalIntent
from assistant_api.analytics import AnalyticsClient


@dataclass(frozen=True)
class AnalyticalExecution:
    intent: AnalyticalIntent
    rows: list[dict]


def execute_analytical_intent(
    intent: AnalyticalIntent,
    client: AnalyticsClient,
) -> AnalyticalExecution:
    handlers = {
        "get_score": _get_score,
        "get_score_factors": _get_score_factors,
        "get_time_series": _get_time_series,
        "compare_periods": _compare_periods,
        "compare_models": _compare_models,
        "rank_territories": _rank_territories,
        "find_largest_increase": _find_largest_increase,
        "get_data_freshness": _get_data_freshness,
        "get_pipeline_status": _get_pipeline_status,
    }
    return AnalyticalExecution(intent=intent, rows=handlers[intent.intent](intent, client))


def _score_filters(intent: AnalyticalIntent, period: str | None = None) -> dict:
    return {
        "geographic_level": intent.geographic_level,
        "geographic_code": intent.geographic_code,
        "reference_period": period,
        "model_version": intent.model_version,
        "active_model_only": intent.model_version is None,
        "include_details": False,
    }


def _get_score(intent, client):
    return client.scores(**_score_filters(intent, intent.period_start), limit=1)


def _get_score_factors(intent, client):
    return [client.score_factors(
        intent.geographic_level,
        intent.geographic_code,
        intent.period_start,
        model_version=intent.model_version,
    )]


def _get_time_series(intent, client):
    response = client.score_series(
        intent.geographic_level,
        intent.geographic_code,
        model_version=intent.model_version,
    )
    return [
        row for row in response.get("series", [])
        if (not intent.period_start or row.get("reference_period", "") >= intent.period_start)
        and (not intent.period_end or row.get("reference_period", "") <= intent.period_end)
    ][:100]


def _compare_periods(intent, client):
    rows = []
    for period in (intent.period_start, intent.period_end):
        rows.extend(client.scores(**_score_filters(intent, period), limit=1))
    if len(rows) == 2 and all(row.get("score") is not None for row in rows):
        rows.append({
            "comparison": "score_change",
            "period_start": intent.period_start,
            "period_end": intent.period_end,
            "change": round(float(rows[1]["score"]) - float(rows[0]["score"]), 8),
        })
    return rows


def _compare_models(intent, client):
    return [client.compare_models(
        version_a=intent.model_version,
        version_b=intent.comparison_model_version,
        geographic_level=intent.geographic_level or "department",
        reference_period=intent.period_start,
    )]


def _rank_territories(intent, client):
    sort = "score_asc" if intent.order == "ascending" else "score_desc"
    return client.scores(
        **_score_filters(intent, intent.period_start),
        sort=sort,
        limit=intent.limit,
    )


def _find_largest_increase(intent, client):
    by_period = []
    for period in (intent.period_start, intent.period_end):
        rows = client.scores(**_score_filters(intent, period), limit=500)
        by_period.append({row["geographic_code"]: row for row in rows})
    changes = []
    for code in by_period[0].keys() & by_period[1].keys():
        before, after = by_period[0][code], by_period[1][code]
        if before.get("score") is None or after.get("score") is None:
            continue
        changes.append({
            "geographic_level": intent.geographic_level,
            "geographic_code": code,
            "geographic_name": after.get("geographic_name"),
            "period_start": intent.period_start,
            "period_end": intent.period_end,
            "score_start": before["score"],
            "score_end": after["score"],
            "change": round(float(after["score"]) - float(before["score"]), 8),
        })
    changes.sort(key=lambda row: row["change"], reverse=intent.order == "descending")
    return changes[:intent.limit]


def _get_data_freshness(intent, client):
    payload = client.observability()
    return payload.get("operational", {}).get("indicator_freshness", [])[:100]


def _get_pipeline_status(intent, client):
    payload = client.observability()
    return [{
        "status": payload.get("status"),
        "generated_at": payload.get("generated_at"),
        "pipeline": payload.get("pipeline", payload.get("operational", {})),
        "document_statuses": payload.get("document_statuses", []),
    }]
