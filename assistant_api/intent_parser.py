"""Deterministic French parser for common analytical questions."""

from __future__ import annotations

import re
import unicodedata

from assistant_api.analytical_intents import AnalyticalIntent


class UnsupportedAnalyticalQuestion(ValueError):
    """Raised when no safe structured intention can represent the question."""


_PERIOD = re.compile(r"\b(?:19|20)\d{2}(?:-(?:0[1-9]|1[0-2]))?\b")
_VERSION = re.compile(r"\b\d+\.\d+\.\d+\b")
_DEPARTMENT = re.compile(r"\b(?:departement|dept)\s+(2[AB]|\d{1,3})\b")
_REGION = re.compile(r"\bregion\s+(\d{1,3})\b")


def parse_analytical_intent(question: str) -> AnalyticalIntent:
    normalized = _normalize(question)
    periods = _PERIOD.findall(normalized)
    versions = _VERSION.findall(normalized)
    level, code = _extract_territory(normalized)

    common = {
        "geographic_level": level,
        "geographic_code": code,
        "period_start": periods[0] if periods else None,
        "period_end": periods[1] if len(periods) > 1 else None,
        "model_version": versions[0] if versions else None,
        "comparison_model_version": versions[1] if len(versions) > 1 else None,
    }
    if "fraicheur" in normalized or "mise a jour" in normalized:
        return AnalyticalIntent(intent="get_data_freshness")
    if "pipeline" in normalized or "import" in normalized:
        return AnalyticalIntent(intent="get_pipeline_status")
    if "modele" in normalized and any(
        term in normalized for term in ("compar", "difference")
    ):
        return AnalyticalIntent(intent="compare_models", **common)
    if any(term in normalized for term in ("plus forte hausse", "plus augmente", "progression maximale")):
        return AnalyticalIntent(intent="find_largest_increase", **common)
    if any(term in normalized for term in ("classement", "classer", "top ", "plus eleve", "plus faible")):
        order = "ascending" if "plus faible" in normalized else "descending"
        return AnalyticalIntent(intent="rank_territories", order=order, **common)
    if any(term in normalized for term in ("compar", "difference", "entre")) and len(periods) >= 2:
        return AnalyticalIntent(intent="compare_periods", **common)
    if any(term in normalized for term in ("facteur", "contribution", "expliquer le score")):
        return AnalyticalIntent(intent="get_score_factors", **common)
    if any(term in normalized for term in ("evolution", "serie", "historique")):
        return AnalyticalIntent(intent="get_time_series", **common)
    if "score" in normalized:
        return AnalyticalIntent(intent="get_score", **common)
    raise UnsupportedAnalyticalQuestion(
        "La question analytique ne correspond à aucune intention autorisée."
    )


def _extract_territory(question: str) -> tuple[str | None, str | None]:
    department = _DEPARTMENT.search(question)
    if department:
        return "department", department.group(1).upper()
    region = _REGION.search(question)
    if region:
        return "region", region.group(1)
    if "departement" in question:
        return "department", None
    if "region" in question:
        return "region", None
    return None, None


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(character for character in decomposed if not unicodedata.combining(character))
