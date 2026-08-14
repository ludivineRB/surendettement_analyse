"""PostgreSQL persistence and lexical retrieval for reviewed chunks."""

from __future__ import annotations

from sqlalchemy import Engine, text

from assistant_api.chunking import CorpusChunk


class EmptyCorpusError(ValueError):
    """Raised when an empty corpus would deactivate every indexed chunk."""


def replace_active_corpus(engine: Engine, chunks: list[CorpusChunk]) -> int:
    if not chunks:
        raise EmptyCorpusError("Refusing to replace the corpus with no chunks")
    records = [
        {
            "chunk_id": chunk.chunk_id,
            "source_id": chunk.source_id,
            "source_url": chunk.source_url,
            "source_title": chunk.source_title,
            "publisher": chunk.publisher,
            "reference_period": chunk.reference_period,
            "geographic_scope": chunk.geographic_scope,
            "section": chunk.section,
            "ordinal": chunk.ordinal,
            "content": chunk.content,
            "content_sha256": chunk.content_sha256,
            "source_sha256": chunk.source_sha256,
        }
        for chunk in chunks
    ]
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE assistant.corpus_chunks SET is_active = FALSE")
        )
        connection.execute(text(_UPSERT_CHUNK_SQL), records)
    return len(records)


def search_active_chunks(
    engine: Engine,
    query: str,
    *,
    limit: int = 5,
) -> list[dict]:
    query = query.strip()
    if not query:
        return []
    bounded_limit = max(1, min(limit, 20))
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                """
                SELECT chunk_id, source_id, source_url, source_title,
                       publisher, reference_period, geographic_scope,
                       section, content,
                       ts_rank_cd(
                           search_vector,
                           websearch_to_tsquery('french', :query)
                       ) AS rank
                FROM assistant.corpus_chunks
                WHERE is_active = TRUE
                  AND search_vector @@ websearch_to_tsquery('french', :query)
                ORDER BY rank DESC, source_id, ordinal
                LIMIT :limit
                """
            ),
            {"query": query, "limit": bounded_limit},
        )
        return [dict(row) for row in rows.mappings().all()]


_UPSERT_CHUNK_SQL = """
INSERT INTO assistant.corpus_chunks (
    chunk_id, source_id, source_url, source_title, publisher,
    reference_period, geographic_scope, section, ordinal, content,
    content_sha256, source_sha256, is_active, indexed_at
) VALUES (
    :chunk_id, :source_id, :source_url, :source_title, :publisher,
    :reference_period, :geographic_scope, :section, :ordinal, :content,
    :content_sha256, :source_sha256, TRUE, CURRENT_TIMESTAMP
)
ON CONFLICT (chunk_id) DO UPDATE SET
    source_url = EXCLUDED.source_url,
    source_title = EXCLUDED.source_title,
    publisher = EXCLUDED.publisher,
    reference_period = EXCLUDED.reference_period,
    geographic_scope = EXCLUDED.geographic_scope,
    section = EXCLUDED.section,
    ordinal = EXCLUDED.ordinal,
    content = EXCLUDED.content,
    content_sha256 = EXCLUDED.content_sha256,
    source_sha256 = EXCLUDED.source_sha256,
    is_active = TRUE,
    indexed_at = CURRENT_TIMESTAMP
"""
