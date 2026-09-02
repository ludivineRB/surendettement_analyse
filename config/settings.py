"""Runtime settings for the Streamlit dashboard."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "processed"

SURENDETTEMENT_LOCAL_CSV = DATA_DIR / "surendettement_unified.csv"
MACRO_LOCAL_CSV = DATA_DIR / "statinfo_departements_bi_curated.csv"

SURENDETTEMENT_API_BASE_URL = os.getenv(
    "SURENDETTEMENT_API_BASE_URL", "http://127.0.0.1:8020"
).rstrip("/")


def build_api_url(path: str, explicit_url: str | None = None) -> str:
    """Build a data API URL while preserving explicit legacy configuration."""
    return explicit_url or f"{SURENDETTEMENT_API_BASE_URL}/{path.lstrip('/')}"


SURENDETTEMENT_API_URL = build_api_url(
    "/api/data/streamlit?limit=50000", os.getenv("SURENDETTEMENT_API_URL")
)
INCLUSION_FINANCIERE_API_URL = build_api_url(
    "/api/data/inclusion-financiere?limit=100000",
    os.getenv("INCLUSION_FINANCIERE_API_URL"),
)
REGIONAL_MACRO_API_URL = build_api_url(
    "/api/data/macro-economic-regions?limit=5000",
    os.getenv("REGIONAL_MACRO_API_URL"),
)

DEPARTMENTS_GEOJSON_URL = os.getenv(
    "DEPARTMENTS_GEOJSON_URL",
    "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/departements.geojson",
)
REGIONS_GEOJSON_URL = os.getenv(
    "REGIONS_GEOJSON_URL",
    "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/regions.geojson",
)

API_TIMEOUT_SECONDS = int(os.getenv("SURENDETTEMENT_API_TIMEOUT", "8"))
