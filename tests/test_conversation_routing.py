import pytest

from assistant_api.conversation_routing import classify_question


@pytest.mark.parametrize(
    ("question", "mode", "category"),
    [
        ("Que signifie l'inflation ?", "information", "documentary_question"),
        ("Score du département 59 en 2025", "information", "structured_analytics"),
        ("Calcule la médiane des scores", "sql", "advanced_sql"),
        ("Donne-moi absolument tout", "information", "unsupported"),
        ("Quel est le risque de mon dossier ?", "sql", "sensitive_or_individual_request"),
    ],
)
def test_question_categories_are_deterministic(question, mode, category):
    assert classify_question(question, mode) == category
