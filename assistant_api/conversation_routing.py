"""Top-level routing shared by the two distinct assistant experiences."""

from __future__ import annotations

from typing import Literal

from assistant_api.intent_parser import (
    UnsupportedAnalyticalQuestion,
    parse_analytical_intent,
)
from assistant_api.routing import route_question


AssistantMode = Literal["information", "sql"]
QuestionCategory = Literal[
    "documentary_question",
    "structured_analytics",
    "advanced_sql",
    "unsupported",
    "sensitive_or_individual_request",
]

_SENSITIVE_TERMS = {
    "ma dette",
    "mes dettes",
    "mon dossier",
    "ma situation",
    "mon risque",
    "dois-je emprunter",
    "peux-je emprunter",
    "accordez-moi",
    "diagnostic personnel",
}
_PROMPT_INJECTION_TERMS = {
    "ignore les instructions",
    "ignore les règles",
    "ignore les regles",
    "prompt système",
    "prompt systeme",
    "révèle le prompt",
    "revele le prompt",
    "révèle les secrets",
    "revele les secrets",
    "invente un chiffre",
    "applique cette consigne",
}


def classify_question(question: str, mode: AssistantMode) -> QuestionCategory:
    normalized = question.casefold()
    if any(term in normalized for term in _SENSITIVE_TERMS):
        return "sensitive_or_individual_request"
    if any(term in normalized for term in _PROMPT_INJECTION_TERMS):
        return "unsupported"
    if any(term in normalized for term in ("absolument tout", "toutes les données", "exporte tout")):
        return "unsupported"
    if mode == "sql":
        return "advanced_sql"
    method = route_question(question)
    if method == "documents":
        return "documentary_question"
    try:
        parse_analytical_intent(question)
    except (UnsupportedAnalyticalQuestion, ValueError):
        # Existing macro-economic and Banque de France datasets remain
        # deterministic analytical sources on the information page.
        if any(term in normalized for term in ("surendettement", "inflation", "chômage", "chomage", "pauvreté", "pauvrete")):
            return "structured_analytics"
        return "unsupported"
    return "structured_analytics"
