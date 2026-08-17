from unittest.mock import Mock, patch

from assistant_api.orchestration import build_grounding_context


@patch("assistant_api.orchestration.search_active_chunks")
def test_document_question_uses_only_reviewed_corpus(search):
    search.return_value = [{"source_id": "insee-definition-ipc"}]
    analytics = Mock()

    context = build_grounding_context(
        "Que signifie l'inflation ?",
        engine=Mock(),
        analytics_client=analytics,
    )

    assert context.method == "documents"
    assert context.documentary_chunks == [
        {"source_id": "insee-definition-ipc"}
    ]
    analytics.fetch.assert_not_called()


@patch("assistant_api.orchestration.search_active_chunks")
def test_hybrid_question_keeps_documents_and_analytics_separate(search):
    search.return_value = [{"source_id": "bdf-typologie"}]
    analytics = Mock()
    analytics.fetch.return_value = [{"value": 42}]

    context = build_grounding_context(
        "Pourquoi le surendettement augmente-t-il en France en 2025 ?",
        engine=Mock(),
        analytics_client=analytics,
    )

    assert context.method == "hybrid"
    assert context.analytics_dataset == "surendettement"
    assert context.analytics_rows == [{"value": 42}]
    analytics.fetch.assert_called_once_with(
        "surendettement",
        filters={"reference_year": 2025},
        limit=500,
    )
