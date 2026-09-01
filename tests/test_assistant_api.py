import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from unittest.mock import Mock, patch

from assistant_api.main import app, answer_question, health, metrics, retrieval_search
from assistant_api.generation import GeneratorUnavailable
from assistant_api.openai_provider import get_text_generator
from assistant_api.storage import get_engine
from assistant_api.schemas import AnswerRequest, RetrievalRequest
from assistant_api.sql_service import SQLClarificationRequired, run_text_to_sql


def test_health_identifies_assistant_service():
    assert health() == {
        "status": "ok",
        "service": "assistant-api",
    }


@pytest.fixture
def http_client():
    app.dependency_overrides[get_engine] = lambda: Mock()
    app.dependency_overrides[get_text_generator] = lambda: Mock()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_health_is_public_and_does_not_call_provider(http_client):
    response = http_client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_answer_http_requires_authentication(http_client, monkeypatch):
    monkeypatch.setenv("ASSISTANT_INTERNAL_TOKEN", "expected-token")

    response = http_client.post(
        "/v1/answers", json={"question": "Question métier"}
    )

    assert response.status_code == 401


def test_answer_http_rejects_incorrect_authentication(http_client, monkeypatch):
    monkeypatch.setenv("ASSISTANT_INTERNAL_TOKEN", "expected-token")

    response = http_client.post(
        "/v1/answers",
        json={"question": "Question métier"},
        headers={"X-Internal-Token": "wrong-token"},
    )

    assert response.status_code == 403


def test_answer_http_validates_input(http_client, monkeypatch):
    monkeypatch.setenv("ASSISTANT_INTERNAL_TOKEN", "expected-token")

    response = http_client.post(
        "/v1/answers",
        json={"question": "x"},
        headers={"X-Internal-Token": "expected-token"},
    )

    assert response.status_code == 422


def test_metrics_contract_is_machine_readable():
    assert isinstance(metrics(), dict)


def test_openapi_documents_answer_authentication_and_decision():
    schema = app.openapi()

    operation = schema["paths"]["/v1/answers"]["post"]
    response_schema = schema["components"]["schemas"]["AnswerResponse"]
    assert {"InternalToken": []} in operation["security"]
    assert response_schema["properties"]["decision"]["enum"] == [
        "execute", "clarify", "refuse"
    ]


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
    assert response.decision == "refuse"
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
    assert response.decision == "execute"
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

    assert error.value.status_code == 401


@patch("assistant_api.sql_service.record_sql_execution")
def test_ambiguous_sql_stops_before_generator_and_database(record_execution):
    generator = Mock()
    readonly_engine = Mock()

    with pytest.raises(SQLClarificationRequired):
        run_text_to_sql(
            "Compare Paris et Lyon.",
            generator=generator,
            readonly_engine=readonly_engine,
            audit_engine=Mock(),
            request_id=Mock(),
            actor_id=None,
            model_version="test",
        )

    generator.generate.assert_not_called()
    readonly_engine.connect.assert_not_called()
    assert record_execution.call_args.args[1]["validation_error"] == (
        "clarification_required"
    )


@patch("assistant_api.sql_service.record_sql_execution")
def test_department_codes_do_not_count_as_a_comparison_period(record_execution):
    generator = Mock()

    with pytest.raises(SQLClarificationRequired, match="période"):
        run_text_to_sql(
            "Compare le score des départements 59 et 62.",
            generator=generator,
            readonly_engine=Mock(),
            audit_engine=Mock(),
            request_id=Mock(),
            actor_id=None,
            model_version="test",
        )

    generator.generate.assert_not_called()


@patch("assistant_api.sql_service.record_sql_execution")
def test_sql_mode_returns_clarification_instead_of_service_error(
    record_execution,
    monkeypatch,
):
    monkeypatch.setenv("ASSISTANT_INTERNAL_TOKEN", "expected-token")

    response = answer_question(
        AnswerRequest(question="Quel territoire va mal ?", mode="sql"),
        Mock(),
        Mock(),
        Mock(),
        x_internal_token="expected-token",
    )

    assert response.method == "refusal"
    assert response.decision == "clarify"
    assert response.category == "advanced_sql"
    assert "indicateur" in response.answer
    assert response.generated_sql is None


@patch("assistant_api.main.build_grounding_context")
def test_provider_error_is_normalized_without_remote_detail(build_context):
    build_context.side_effect = GeneratorUnavailable("secret-remote-detail")

    with pytest.raises(HTTPException) as error:
        answer_question(
            AnswerRequest(question="Expliquez le taux de chômage"),
            Mock(),
            Mock(),
            Mock(),
        )

    assert error.value.status_code == 503
    assert error.value.detail == "Service IA temporairement indisponible."
    assert "secret" not in str(error.value.detail)


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
