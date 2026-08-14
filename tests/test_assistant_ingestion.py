from unittest.mock import Mock, patch

import pytest

from assistant_api.corpus import CorpusSource
from assistant_api.ingestion import (
    FetchedDocument,
    SourceRetrievalError,
    SourceRevisionChanged,
    fetch_source,
    verify_reviewed_revision,
)


def source():
    return CorpusSource(
        id="insee-test",
        publisher="Insee",
        title="Définition officielle de test",
        url="https://www.insee.fr/fr/test",
        document_type="definition",
        published_at="2026-01-01",
        reference_period="2026",
        geographic_scope="France",
        topics=["test"],
        usage="documents",
        reviewed_at="2026-08-14",
        normalized_characters=100,
        content_sha256="a" * 64,
    )


@patch("assistant_api.ingestion.requests.get")
def test_fetch_source_keeps_main_content_and_provenance(mock_get):
    response = Mock()
    response.headers = {"Content-Type": "text/html; charset=utf-8"}
    response.content = (
        b"<html><main><nav>Menu</nav><h1>Definition</h1>"
        + b"<p>Contenu metier verifie. </p>" * 20
        + b"</main></html>"
    )
    response.raise_for_status.return_value = None
    mock_get.return_value = response

    document = fetch_source(source())

    assert document.source_id == "insee-test"
    assert document.source_url == "https://www.insee.fr/fr/test"
    assert "Menu" not in document.content
    assert len(document.content_sha256) == 64


@patch("assistant_api.ingestion.requests.get")
def test_fetch_source_refuses_non_html_content(mock_get):
    response = Mock()
    response.headers = {"Content-Type": "application/pdf"}
    response.content = b"PDF"
    response.raise_for_status.return_value = None
    mock_get.return_value = response

    with pytest.raises(SourceRetrievalError, match="content type"):
        fetch_source(source())


@patch("assistant_api.ingestion.requests.get")
def test_fetch_source_accepts_concise_official_definition(mock_get):
    response = Mock()
    response.headers = {"Content-Type": "text/html"}
    response.content = (
        b"<main><h1>Taux</h1><p>Le taux rapporte une population "
        b"a une population de reference clairement definie.</p></main>"
    )
    response.raise_for_status.return_value = None
    mock_get.return_value = response

    document = fetch_source(source())

    assert "population de reference" in document.content


def test_reviewed_source_change_requires_new_approval():
    document = FetchedDocument(
        source_id="insee-test",
        source_url="https://www.insee.fr/fr/test",
        title="Définition officielle de test",
        content="Contenu modifié",
        content_sha256="b" * 64,
    )

    with pytest.raises(SourceRevisionChanged, match="approved again"):
        verify_reviewed_revision(source(), document)
