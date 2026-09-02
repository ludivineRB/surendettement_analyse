"""Allow-listed client for the project's structured analytics API."""

from __future__ import annotations

import os
from typing import Literal
from urllib.parse import quote

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
        payload = self._get(_DATASET_PATHS[dataset], params)
        if not isinstance(payload, list):
            raise AnalyticsUnavailable(
                "Le service analytique a renvoyé un format inattendu."
            )
        return payload

    def scores(self, **filters) -> list[dict]:
        params = {key: value for key, value in filters.items() if value is not None}
        params["limit"] = max(1, min(int(params.get("limit", 10)), 500))
        payload = self._get("/api/risk-scores", params)
        if not isinstance(payload, list):
            raise AnalyticsUnavailable("Format de scores inattendu.")
        return payload

    def score_factors(
        self,
        geographic_level: str,
        geographic_code: str,
        reference_period: str,
        *,
        model_version: str | None = None,
    ) -> dict:
        path = "/api/risk-score-factors/{}/{}/{}".format(
            quote(geographic_level, safe=""),
            quote(geographic_code, safe=""),
            quote(reference_period, safe=""),
        )
        payload = self._get(path, {"model_version": model_version})
        return self._expect_object(payload)

    def score_series(
        self,
        geographic_level: str,
        geographic_code: str,
        *,
        model_version: str | None = None,
    ) -> dict:
        path = "/api/risk-score-series/{}/{}".format(
            quote(geographic_level, safe=""),
            quote(geographic_code, safe=""),
        )
        payload = self._get(path, {"model_version": model_version})
        return self._expect_object(payload)

    def compare_models(self, **filters) -> dict:
        payload = self._get(
            "/api/risk-score-model-comparison",
            {key: value for key, value in filters.items() if value is not None},
        )
        return self._expect_object(payload)

    def observability(self) -> dict:
        return self._expect_object(self._get("/api/data/observability", {}))

    def _get(self, path: str, params: dict) -> object:
        try:
            internal_token = os.getenv("ASSISTANT_INTERNAL_TOKEN", "").strip()
            headers = (
                {"X-Internal-Token": internal_token}
                if internal_token
                else None
            )
            request_params = {
                key: value for key, value in params.items() if value is not None
            }
            if headers:
                response = requests.get(
                    f"{self.base_url}{path}",
                    params=request_params,
                    headers=headers,
                    timeout=self.timeout_seconds,
                )
            else:
                response = requests.get(
                    f"{self.base_url}{path}",
                    params=request_params,
                    timeout=self.timeout_seconds,
                )
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            raise AnalyticsUnavailable(
                "Le service analytique est indisponible."
            ) from exc

    @staticmethod
    def _expect_object(payload: object) -> dict:
        if not isinstance(payload, dict):
            raise AnalyticsUnavailable("Le service analytique a renvoyé un format inattendu.")
        return payload
