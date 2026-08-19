import pytest
from pydantic import ValidationError

from assistant_api.analytical_intents import AnalyticalIntent
from assistant_api.intent_parser import (
    UnsupportedAnalyticalQuestion,
    parse_analytical_intent,
)


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("Quel est le score du département 59 en 2025-02 ?", "get_score"),
        ("Quels facteurs expliquent le score du département 59 en 2025 ?", "get_score_factors"),
        ("Montre l'évolution du score de la région 32", "get_time_series"),
        ("Compare le département 59 entre 2024 et 2025", "compare_periods"),
        ("Compare les modèles 1.1.0 et 1.2.0", "compare_models"),
        ("Top des départements en 2025", "rank_territories"),
        ("Plus forte hausse par région entre 2024 et 2025", "find_largest_increase"),
        ("Quelle est la fraîcheur des données ?", "get_data_freshness"),
        ("Quel est le statut du pipeline d'import ?", "get_pipeline_status"),
    ],
)
def test_parser_recognizes_allowlisted_intents(question, expected):
    assert parse_analytical_intent(question).intent == expected


def test_parser_extracts_bounded_parameters():
    intent = parse_analytical_intent(
        "Classement des départements avec les scores les plus faibles en 2025"
    )
    assert intent.geographic_level == "department"
    assert intent.period_start == "2025"
    assert intent.order == "ascending"
    assert intent.limit == 10


def test_contract_forbids_unknown_fields_and_excessive_limit():
    with pytest.raises(ValidationError):
        AnalyticalIntent(
            intent="rank_territories",
            geographic_level="department",
            period_start="2025",
            limit=1000,
            sql="SELECT *",
        )


def test_unsupported_question_is_rejected():
    with pytest.raises(UnsupportedAnalyticalQuestion):
        parse_analytical_intent("Donne-moi toutes les données disponibles")
