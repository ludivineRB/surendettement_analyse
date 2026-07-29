"""Data loading and preparation for the Streamlit dashboard."""

from __future__ import annotations

import math

import pandas as pd
import requests
import streamlit as st

from config.settings import (
    API_TIMEOUT_SECONDS,
    INCLUSION_FINANCIERE_API_URL,
    MACRO_LOCAL_CSV,
    REGIONAL_MACRO_API_URL,
    SURENDETTEMENT_LOCAL_CSV,
)
from src.api.surendettement_client import SurendettementApiError, fetch_surendettement_api
from src.utils.departments import add_department_code, normalize_department_code

MEASURE_OPTIONS = {
    "Nombre de dossiers déposés": "surendettement_value",
}


@st.cache_data(show_spinner=False, ttl=300)
def load_inclusion_financiere_data() -> tuple[pd.DataFrame, list[str]]:
    """Load and normalize monthly regional financial-inclusion observations."""
    try:
        response = requests.get(INCLUSION_FINANCIERE_API_URL, timeout=API_TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        return pd.DataFrame(), [f"API inclusion financière indisponible : {exc}"]

    if not isinstance(payload, list):
        return pd.DataFrame(), ["La réponse inclusion financière n'est pas une liste."]

    data = pd.DataFrame(payload)
    required = {
        "reference_period",
        "region_code",
        "region_name",
        "indicator_code",
        "indicator_label",
        "value",
    }
    missing = sorted(required.difference(data.columns))
    if missing:
        return pd.DataFrame(), [f"Colonnes API manquantes : {', '.join(missing)}"]

    data["value"] = pd.to_numeric(data["value"], errors="coerce")
    data["reference_period"] = data["reference_period"].astype(str)
    data = data.dropna(subset=["value"]).sort_values(
        ["reference_period", "region_code", "indicator_code"]
    )
    return data, [f"{len(data)} observations mensuelles chargées depuis l'API."]


@st.cache_data(show_spinner=False, ttl=300)
def load_regional_macro_data() -> tuple[pd.DataFrame, list[str]]:
    """Load the curated INSEE indicators aggregated to the regional level."""
    try:
        response = requests.get(REGIONAL_MACRO_API_URL, timeout=API_TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        return pd.DataFrame(), [f"API macro régionale indisponible : {exc}"]

    if not isinstance(payload, list):
        return pd.DataFrame(), ["La réponse macro régionale n'est pas une liste."]

    data = pd.DataFrame(payload)
    required = {
        "reference_year",
        "region_code",
        "region_name",
        "indicator_code",
        "indicator_name",
        "value",
    }
    missing = sorted(required.difference(data.columns))
    if missing:
        return pd.DataFrame(), [f"Colonnes macro manquantes : {', '.join(missing)}"]

    data["value"] = pd.to_numeric(data["value"], errors="coerce")
    data["reference_year"] = pd.to_numeric(data["reference_year"], errors="coerce").astype("Int64")
    data = data.dropna(subset=["value", "reference_year"]).sort_values(
        ["reference_year", "region_code", "indicator_code"]
    )
    return data, [f"{len(data)} valeurs macro régionales chargées depuis l'API."]


@st.cache_data(show_spinner=False)
def load_dashboard_data(use_api: bool = True) -> tuple[pd.DataFrame, list[str]]:
    """Load API/local data, normalize keys and return dashboard-ready rows."""
    messages: list[str] = []

    if use_api:
        try:
            api_df = fetch_surendettement_api()
            prepared = _prepare_api_data(api_df)
            if not prepared.empty:
                return prepared, ["Données chargées depuis l'API."]
        except SurendettementApiError as exc:
            messages.append(str(exc))

    try:
        prepared = _prepare_local_data()
        if not prepared.empty:
            messages.append("Données chargées depuis les fichiers locaux.")
            messages.extend(validate_join(prepared))
            return prepared, messages
    except FileNotFoundError:
        messages.append("Fichiers locaux absents. Exemple de démonstration affiché.")

    return _make_sample_data(), messages


def validate_join(df: pd.DataFrame) -> list[str]:
    """Return business-readable warnings about missing join keys or values."""
    messages: list[str] = []
    missing_dept = int(df["departement_code"].isna().sum())
    missing_year = int(df["reference_year"].isna().sum())
    missing_macro = int(df["macro_value"].isna().sum())

    if missing_dept:
        messages.append(f"{missing_dept} lignes sans code département normalisé.")
    if missing_year:
        messages.append(f"{missing_year} lignes sans année exploitable.")
    if missing_macro:
        messages.append(f"{missing_macro} lignes sans valeur macro-économique.")
    return messages


def _prepare_local_data() -> pd.DataFrame:
    sur = pd.read_csv(SURENDETTEMENT_LOCAL_CSV)
    macro = pd.read_csv(MACRO_LOCAL_CSV)

    sur = add_department_code(sur, "departement")
    sur["reference_year"] = pd.to_numeric(sur["year"], errors="coerce").astype("Int64")
    sur["value"] = pd.to_numeric(sur["value"], errors="coerce")
    sur = (
        sur.dropna(subset=["departement_code", "reference_year"])
        .groupby(["reference_year", "departement_code"], as_index=False)["value"]
        .sum()
        .rename(columns={"value": "surendettement_value"})
    )

    macro["departement_code"] = macro["departement_code"].map(normalize_department_code)
    macro["reference_year"] = pd.to_numeric(macro["reference_year"], errors="coerce").astype("Int64")
    macro["macro_value"] = pd.to_numeric(macro["value"], errors="coerce")
    macro = (
        macro.dropna(subset=["departement_code", "reference_year", "indicator_code"])
        .groupby(
            [
                "reference_year",
                "departement_code",
                "departement_name",
                "indicator_code",
                "indicator_name",
            ],
            as_index=False,
        )["macro_value"]
        .mean()
    )

    merged = macro.merge(sur, on=["reference_year", "departement_code"], how="left")
    merged["surendettement_value"] = merged["surendettement_value"].fillna(0)
    return _finalize_dataset(merged)


def _prepare_api_data(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    output = df.copy()
    output["departement_code"] = output.get("departement_code", pd.Series(dtype=str)).map(
        normalize_department_code
    )
    output["reference_year"] = pd.to_numeric(
        output.get("reference_year", output.get("bdf_reference_year")),
        errors="coerce",
    ).astype("Int64")
    output["departement_name"] = output.get("departement_name", output["departement_code"])
    output["indicator_code"] = output.get("macro_indicator_code", output.get("indicator_code", "macro"))
    output["indicator_name"] = output.get("macro_indicator_name", output.get("indicator_name", "Indicateur macro"))
    output["macro_value"] = pd.to_numeric(
        output.get("macro_value", output.get("value", output.get("insee_value"))),
        errors="coerce",
    )
    output["surendettement_value"] = pd.to_numeric(
        output.get(
            "dossiers_deposes",
            output.get("surendettement_value", output.get("dossiers_surendettement")),
        ),
        errors="coerce",
    ).fillna(0)
    return _finalize_dataset(output)


def _finalize_dataset(df: pd.DataFrame) -> pd.DataFrame:
    output = df.copy()
    output = output.dropna(subset=["reference_year", "departement_code", "indicator_code"])
    output["reference_year"] = output["reference_year"].astype(int)
    output["macro_indicator_label"] = output.apply(_readable_indicator_label, axis=1)
    output["national_surendettement_mean"] = output.groupby("reference_year")[
        "surendettement_value"
    ].transform("mean")
    output["national_macro_mean"] = output.groupby(["reference_year", "indicator_code"])[
        "macro_value"
    ].transform("mean")
    output["annual_change_pct"] = (
        output.sort_values("reference_year")
        .groupby(["departement_code", "indicator_code"])["surendettement_value"]
        .pct_change()
        .replace([math.inf, -math.inf], pd.NA)
        .fillna(0)
        * 100
    )
    return output


def _readable_indicator_label(row: pd.Series) -> str:
    indicator_code = str(row.get("indicator_code", "")).strip()
    indicator_name = str(row.get("indicator_name", "")).strip()
    if indicator_name and indicator_name.lower() != "nan" and indicator_name != indicator_code:
        return indicator_name
    return f"Indicateur INSEE non libellé ({indicator_code})"


def _make_sample_data() -> pd.DataFrame:
    rows = []
    departments = [("01", "Ain"), ("13", "Bouches-du-Rhône"), ("33", "Gironde"), ("59", "Nord"), ("75", "Paris")]
    indicators = [("tx_chomage", "Taux de chômage"), ("revenu_median", "Revenu médian")]
    for year in range(2021, 2026):
        for dept_code, dept_name in departments:
            for indicator_code, indicator_name in indicators:
                base = int(dept_code) if dept_code.isdigit() else 20
                rows.append(
                    {
                        "reference_year": year,
                        "departement_code": dept_code,
                        "departement_name": dept_name,
                        "indicator_code": indicator_code,
                        "indicator_name": indicator_name,
                        "macro_value": base * 0.8 + (year - 2020) * 1.5,
                        "surendettement_value": base * 12 + (year - 2020) * 9,
                    }
                )
    return _finalize_dataset(pd.DataFrame(rows))
