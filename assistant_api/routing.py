"""Deterministic first-pass routing for business questions."""

from typing import Literal


AnswerMethod = Literal["documents", "analytics", "hybrid", "advanced_sql"]

_ANALYTICS_TERMS = {
    "combien",
    "évolution",
    "evolution",
    "nombre",
    "taux",
    "score",
    "série",
    "serie",
    "département",
    "departement",
    "région",
    "region",
    "france",
    "année",
    "annee",
    "fraîcheur",
    "fraicheur",
    "mise à jour",
    "mise a jour",
    "pipeline",
    "import",
    "classement",
    "top ",
    "modèle",
    "modele",
}
_INTERPRETATION_TERMS = {
    "cause",
    "expliquer",
    "explication",
    "facteur",
    "interpréter",
    "interpreter",
    "pourquoi",
}


def route_question(question: str) -> AnswerMethod:
    normalized = question.casefold()
    requests_analytics = any(
        term in normalized for term in _ANALYTICS_TERMS
    ) or any(character.isdigit() for character in normalized)
    requests_interpretation = any(
        term in normalized for term in _INTERPRETATION_TERMS
    )

    if requests_analytics and requests_interpretation:
        return "hybrid"
    if requests_analytics:
        return "analytics"
    return "documents"
