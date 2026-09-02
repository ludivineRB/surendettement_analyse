"""Client for the surendettement analytical API."""

from __future__ import annotations

import pandas as pd
import requests

from config.settings import (
    ANALYTICS_API_TOKEN,
    API_TIMEOUT_SECONDS,
    SURENDETTEMENT_API_URL,
)


class SurendettementApiError(RuntimeError):
    """Raised when the analytical API cannot be consumed."""


def fetch_surendettement_api(api_url: str = SURENDETTEMENT_API_URL) -> pd.DataFrame:
    """Fetch joined analytical rows from the API and return a dataframe."""
    try:
        response = requests.get(
            api_url,
            timeout=API_TIMEOUT_SECONDS,
            headers={"X-Internal-Token": ANALYTICS_API_TOKEN},
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise SurendettementApiError(
            "L'API surendettement est indisponible. Les données locales seront utilisées."
        ) from exc

    payload = response.json()
    if not isinstance(payload, list):
        raise SurendettementApiError("La réponse de l'API n'a pas le format attendu.")

    return pd.DataFrame(payload)
