from assistant_api.chunking import chunk_document
from assistant_api.corpus import CorpusSource
from assistant_api.ingestion import FetchedDocument


def test_chunks_keep_stable_source_and_section_provenance():
    source = CorpusSource(
        id="insee-definition-test",
        publisher="Insee",
        title="Indicateur de test",
        url="https://www.insee.fr/fr/test",
        document_type="definition",
        published_at="2026-01-01",
        reference_period="2026",
        geographic_scope="France",
        topics=["test"],
        usage="documents",
        reviewed_at="2026-08-14",
        normalized_characters=400,
        content_sha256="a" * 64,
    )
    document = FetchedDocument(
        source_id=source.id,
        source_url=source.url,
        title=source.title,
        content=(
            "# Indicateur de test\n\nIntroduction.\n\n"
            "## Définition\n\n" + "Contenu métier. " * 30
        ),
        content_sha256="a" * 64,
    )

    first = chunk_document(source, document, max_characters=300)
    second = chunk_document(source, document, max_characters=300)

    assert first == second
    assert {chunk.source_id for chunk in first} == {source.id}
    assert any(chunk.section == "Définition" for chunk in first)
    assert all(len(chunk.chunk_id) == 64 for chunk in first)
