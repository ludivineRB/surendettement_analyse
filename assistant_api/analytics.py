"""Allow-listed client for the project's structured analytics API."""

from __future__ import annotations

import os
from typing import Literal

import requests


AnalyticsDataset = Literal[
    "indicators",
    "macro-economic",
    "surendettement",
]

_DATASET_PATHS: dict[AnalyticsDataset, str] = {
    "indicators": "/api/data/indicators",
    "macro-economic": "/api/data/macro-economic",
    "surendettement": "/api/data/surendettement",
}


class AnalyticsUnavailable(RuntimeError):
    """Raised when the structured analytics service cannot answer safely."""


class AnalyticsClient:
    def __init__(
        self,
        base_url: str | None = None,
        timeout_seconds: float = 5,
    ) -> None:
        self.base_url = (
            base_url
            or os.getenv("ANALYTICS_API_BASE_URL")
            or "http://api:8020"
        ).rstrip("/")
        self.timeout_seconds = timeout_seconds

    def fetch(
        self,
        dataset: AnalyticsDataset,
        *,
        filters: dict[str, str | int] | None = None,
        limit: int = 100,
    ) -> list[dict]:
        params = dict(filters or {})
        params["limit"] = max(1, min(limit, 500))
        try:
            response = requests.get(
                f"{self.base_url}{_DATASET_PATHS[dataset]}",
                params=params,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise AnalyticsUnavailable(
                "Le service analytique est indisponible."
            ) from exc
        if not isinstance(payload, list):
            raise AnalyticsUnavailable(
                "Le service analytique a renvoyé un format inattendu."
            )
        return payload
