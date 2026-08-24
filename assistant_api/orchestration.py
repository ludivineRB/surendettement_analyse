"""Build grounded evidence without generating an answer."""

from __future__ import annotations

from dataclasses import dataclass
import re

from sqlalchemy import Engine

from assistant_api.analytical_intents import AnalyticalIntent
from assistant_api.analytics import AnalyticsClient, AnalyticsDataset
from assistant_api.intent_executor import execute_analytical_intent
from assistant_api.intent_parser import (
    UnsupportedAnalyticalQuestion,
    parse_analytical_intent,
)
from assistant_api.repository import search_active_chunks
from assistant_api.routing import AnswerMethod, route_question


_YEAR = re.compile(r"\b(19|20)\d{2}\b")


@dataclass(frozen=True)
class GroundingContext:
    method: AnswerMethod
    documentary_chunks: list[dict]
    analytics_dataset: AnalyticsDataset | None
    analytics_rows: list[dict]
    analytical_intent: AnalyticalIntent | None = None
    analytical_sql: str | None = None


def build_grounding_context(
    question: str,
    *,
    engine: Engine,
    analytics_client: AnalyticsClient,
) -> GroundingContext:
    method = route_question(question)
    documentary_chunks = (
        search_active_chunks(engine, question, limit=5)
        if method in {"documents", "hybrid"}
        else []
    )
    analytics_dataset = None
    analytics_rows: list[dict] = []
    analytical_intent = None
    if method in {"analytics", "hybrid"}:
        try:
            analytical_intent = parse_analytical_intent(question)
        except UnsupportedAnalyticalQuestion:
            analytics_dataset = _select_dataset(question)
            filters = _extract_filters(question)
            analytics_rows = analytics_client.fetch(
                analytics_dataset,
                filters=filters,
                limit=500,
            )
        else:
            execution = execute_analytical_intent(
                analytical_intent,
                analytics_client,
            )
            analytics_rows = execution.rows
    return GroundingContext(
        method=method,
        documentary_chunks=documentary_chunks,
        analytics_dataset=analytics_dataset,
        analytics_rows=analytics_rows,
        analytical_intent=analytical_intent,
    )


def _select_dataset(question: str) -> AnalyticsDataset:
    normalized = question.casefold()
    if any(
        term in normalized
        for term in ("surendettement", "dossier", "dette")
    ):
        return "surendettement"
    return "macro-economic"


def _extract_filters(question: str) -> dict[str, int]:
    match = _YEAR.search(question)
    return {"reference_year": int(match.group())} if match else {}
