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

SURENDETTEMENT_API_URL = os.getenv(
    "SURENDETTEMENT_API_URL",
    "http://127.0.0.1:8020/api/data/streamlit?limit=50000",
)
INCLUSION_FINANCIERE_API_URL = os.getenv(
    "INCLUSION_FINANCIERE_API_URL",
    "http://127.0.0.1:8020/api/data/inclusion-financiere?limit=100000",
)
REGIONAL_MACRO_API_URL = os.getenv(
    "REGIONAL_MACRO_API_URL",
    "http://127.0.0.1:8020/api/data/macro-economic-regions?limit=5000",
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
