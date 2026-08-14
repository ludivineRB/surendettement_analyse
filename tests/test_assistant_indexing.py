import pytest

from assistant_api.corpus import load_registry
from assistant_api.indexing import prepare_registry_chunks
from assistant_api.ingestion import FetchedDocument, SourceRevisionChanged


def test_prepare_registry_requires_every_reviewed_revision(tmp_path):
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(
        """
        {
          "schema_version": "1.0",
          "review_status": "content_reviewed",
          "sources": [{
            "id": "insee-test",
            "publisher": "Insee",
            "title": "Définition officielle",
            "url": "https://www.insee.fr/fr/test",
            "document_type": "definition",
            "published_at": "2026-01-01",
            "reference_period": "2026",
            "geographic_scope": "France",
            "topics": ["test"],
            "usage": "documents",
            "reviewed_at": "2026-08-14",
            "normalized_characters": 100,
            "content_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
          }]
        }
        """,
        encoding="utf-8",
    )
    registry = load_registry(registry_path)

    def changed_source(source):
        return FetchedDocument(
            source_id=source.id,
            source_url=source.url,
            title=source.title,
            content="# Définition\n\n" + "Contenu modifié. " * 10,
            content_sha256="b" * 64,
        )

    with pytest.raises(SourceRevisionChanged):
        prepare_registry_chunks(registry, fetcher=changed_source)


def test_prepared_chunks_include_storage_provenance(tmp_path):
    registry_path = tmp_path / "registry.json"
    content = "# Définition\n\n" + "Contenu officiel. " * 10
    from hashlib import sha256

    content_sha = sha256(content.encode()).hexdigest()
    registry_path.write_text(
        f"""
        {{"schema_version":"1.0","review_status":"content_reviewed","sources":[{{
          "id":"insee-test","publisher":"Insee","title":"Définition officielle",
          "url":"https://www.insee.fr/fr/test","document_type":"definition",
          "published_at":"2026-01-01","reference_period":"2026",
          "geographic_scope":"France","topics":["test"],"usage":"documents",
          "reviewed_at":"2026-08-14","normalized_characters":{len(content)},
          "content_sha256":"{content_sha}"}}]}}
        """,
        encoding="utf-8",
    )
    registry = load_registry(registry_path)
    chunks = prepare_registry_chunks(
        registry,
        fetcher=lambda source: FetchedDocument(
            source.id, source.url, source.title, content, content_sha
        ),
    )

    assert chunks[0].publisher == "Insee"
    assert chunks[0].geographic_scope == "France"
    assert chunks[0].source_sha256 == content_sha
