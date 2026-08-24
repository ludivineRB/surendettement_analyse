"""HTTP client for the existing FastAPI analytical service."""

from __future__ import annotations

import logging
from time import monotonic
from urllib.parse import quote

import requests
from django.conf import settings

from web.analytics.contracts import (
    validate_comparison,
    validate_factors,
    validate_models,
    validate_observability,
    validate_scores,
    validate_series,
    validate_territorial_rows,
)

logger = logging.getLogger(__name__)


class AnalyticsAPIError(RuntimeError):
    """Stable application error for unavailable or invalid API responses."""


class AnalyticsClient:
    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
        session=None,
    ):
        self.base_url = (
            base_url or settings.ANALYTICS_API_BASE_URL
        ).rstrip("/")
        self.timeout = timeout or settings.ANALYTICS_API_TIMEOUT_SECONDS
        self.session = session or requests.Session()

    def list_models(self, active_only: bool = False) -> list[dict]:
        return self._get(
            "/api/risk-score-models",
            {"active_only": str(active_only).lower()},
            validate_models,
        )

    def list_scores(self, **filters) -> list[dict]:
        params = {
            key: value
            for key, value in filters.items()
            if value not in (None, "")
        }
        params.setdefault("limit", 5000)
        return self._get("/api/risk-scores", params, validate_scores)

    def get_series(
        self,
        geographic_level: str,
        geographic_code: str,
        model_code: str = "default",
        model_version: str | None = None,
    ) -> dict:
        path = (
            "/api/risk-score-series/"
            f"{quote(geographic_level, safe='')}/"
            f"{quote(geographic_code, safe='')}"
        )
        return self._get(
            path,
            {"model_code": model_code, "model_version": model_version},
            validate_series,
        )

    def get_factors(
        self,
        geographic_level: str,
        geographic_code: str,
        reference_period: str,
        model_code: str = "default",
        model_version: str | None = None,
    ) -> dict:
        path = (
            "/api/risk-score-factors/"
            f"{quote(geographic_level, safe='')}/"
            f"{quote(geographic_code, safe='')}/"
            f"{quote(reference_period, safe='')}"
        )
        return self._get(
            path,
            {"model_code": model_code, "model_version": model_version},
            validate_factors,
        )

    def compare_models(self, **filters) -> dict:
        return self._get(
            "/api/risk-score-model-comparison",
            {
                key: value
                for key, value in filters.items()
                if value not in (None, "")
            },
            validate_comparison,
        )

    def get_observability(self) -> dict:
        return self._get(
            "/api/data/observability",
            None,
            validate_observability,
        )

    def territorial_indicator_catalog(self) -> list[dict]:
        return self._get(
            "/api/data/territorial-indicators/catalog", None, validate_territorial_rows
        )

    def territorial_indicator_data(self, **filters) -> list[dict]:
        return self._get(
            "/api/data/territorial-indicators/data",
            {key: value for key, value in filters.items() if value not in (None, "")},
            validate_territorial_rows,
        )

    def _get(self, path: str, params: dict | None, validator):
        started = monotonic()
        try:
            response = self.session.get(
                f"{self.base_url}{path}",
                params=params,
                timeout=self.timeout,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            payload = response.json()
            validated = validator(payload)
        except requests.Timeout as exc:
            logger.warning("Analytical API timeout path=%s", path)
            raise AnalyticsAPIError("Le service analytique ne répond pas.") from exc
        except ValueError as exc:
            logger.error("Invalid analytical API response path=%s", path)
            raise AnalyticsAPIError(
                "La réponse du service analytique est invalide."
            ) from exc
        except requests.RequestException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            logger.warning(
                "Analytical API request failed path=%s status=%s",
                path,
                status,
            )
            raise AnalyticsAPIError(
                "Le service analytique est temporairement indisponible."
            ) from exc
        logger.info(
            "Analytical API request path=%s duration_ms=%d",
            path,
            round((monotonic() - started) * 1000),
        )
        return validated
