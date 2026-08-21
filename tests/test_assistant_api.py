import pytest
from fastapi import HTTPException

from unittest.mock import Mock, patch

from assistant_api.main import answer_question, health, metrics, retrieval_search
from assistant_api.schemas import AnswerRequest, RetrievalRequest


def test_health_identifies_assistant_service():
    assert health() == {
        "status": "ok",
        "service": "assistant-api",
    }


def test_metrics_contract_is_machine_readable():
    assert isinstance(metrics(), dict)


def test_answer_request_accepts_django_numeric_conversation_id():
    request = AnswerRequest(
        question="Quel est le score ?",
        conversation_id="42",
    )
    assert request.conversation_id == "42"


def test_answer_refuses_to_invent_when_no_approved_evidence_exists():
    request = AnswerRequest(
        question="Quel est le taux de chômage en France ?"
    )
    analytics = Mock()
    analytics.fetch.return_value = []
    response = answer_question(request, Mock(), analytics, Mock())

    assert response.method == "refusal"
    assert response.category == "structured_analytics"
    assert response.sources == []
    assert response.data_references == []


@patch("assistant_api.main.build_grounding_context")
def test_answer_returns_method_and_citations(build_context):
    from assistant_api.orchestration import GroundingContext

    build_context.return_value = GroundingContext(
        method="documents",
        documentary_chunks=[
            {
                "source_title": "Définition IPC",
                "source_url": "https://www.insee.fr/fr/test",
                "publisher": "Insee",
                "reference_period": "2026",
                "section": "Définition",
                "content": "Contenu",
            }
        ],
        analytics_dataset=None,
        analytics_rows=[],
    )
    generator = Mock()
    generator.generate.return_value = "Réponse [S1]"

    response = answer_question(
        AnswerRequest(question="Définissez l'IPC"),
        Mock(),
        Mock(),
        generator,
    )

    assert response.method == "documents"
    assert response.answer == "Réponse [S1]"
    assert response.sources[0].publisher == "Insee"


@patch("assistant_api.main.build_grounding_context")
def test_structured_score_reference_keeps_territory_name(build_context):
    from assistant_api.analytical_intents import AnalyticalIntent
    from assistant_api.orchestration import GroundingContext

    build_context.return_value = GroundingContext(
        method="analytics",
        documentary_chunks=[],
        analytics_dataset=None,
        analytics_rows=[
            {
                "geographic_code": "59",
                "geographic_name": "Nord",
                "reference_period": "2025",
                "score": 42,
            }
        ],
        analytical_intent=AnalyticalIntent(
            intent="get_score",
            geographic_level="department",
            geographic_code="59",
            period_start="2025",
        ),
    )

    generator = Mock()
    generator.generate.return_value = "Le score est 42 [D1]"
    response = answer_question(
        AnswerRequest(question="Quel est le score du département 59 en 2025 ?"),
        Mock(),
        Mock(),
        generator,
    )

    assert response.data_references[0].indicator_code == "risk_score"
    assert response.data_references[0].territory == "Nord"
    assert response.data_references[0].reference_period == "2025"


def test_sql_mode_rejects_missing_internal_token(monkeypatch):
    monkeypatch.setenv("ASSISTANT_INTERNAL_TOKEN", "expected-token")

    with pytest.raises(HTTPException) as error:
        answer_question(
            AnswerRequest(question="Calcule la médiane", mode="sql"),
            Mock(),
            Mock(),
            Mock(),
            x_internal_token=None,
        )

    assert error.value.status_code == 403


@patch("assistant_api.main.search_active_chunks")
def test_retrieval_returns_ranked_cited_chunks(search):
    search.return_value = [
        {
            "chunk_id": "a" * 64,
            "source_id": "insee-definition-ipc",
            "source_url": "https://www.insee.fr/fr/metadonnees/definition/c1557",
            "source_title": "Prix à la consommation (Indice des)",
            "publisher": "Insee",
            "reference_period": "base 2025",
            "geographic_scope": "France",
            "section": "Définition",
            "content": "L'IPC est un instrument de mesure.",
            "rank": 0.8,
        }
    ]

    response = retrieval_search(
        RetrievalRequest(query="inflation", limit=3),
        Mock(),
    )

    assert response.results[0].publisher == "Insee"
    assert str(response.results[0].source_url).startswith("https://")
    search.assert_called_once()
