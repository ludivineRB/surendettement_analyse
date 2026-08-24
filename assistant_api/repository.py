"""PostgreSQL persistence and lexical retrieval for reviewed chunks."""

from __future__ import annotations

from sqlalchemy import Engine, text
from time import monotonic

from assistant_api.chunking import CorpusChunk
from assistant_api.monitoring import metrics


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
    expanded_query = _expand_business_query(query)
    bounded_limit = max(1, min(limit, 20))
    started = monotonic()
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                """
                WITH normalized_query AS (
                    SELECT to_tsquery(
                        'french',
                        array_to_string(
                            tsvector_to_array(
                                to_tsvector('french', :query)
                            ),
                            ' | '
                        )
                    ) AS value
                )
                , ranked_chunks AS (
                    SELECT chunk_id, source_id, source_url, source_title,
                           publisher, reference_period, geographic_scope,
                           section, content,
                           ts_rank_cd(
                               search_vector,
                               normalized_query.value
                           ) AS rank,
                           row_number() OVER (
                               PARTITION BY source_id
                               ORDER BY ts_rank_cd(
                                   search_vector,
                                   normalized_query.value
                               ) DESC, ordinal
                           ) AS source_position
                    FROM assistant.corpus_chunks
                    CROSS JOIN normalized_query
                    WHERE is_active = TRUE
                      AND search_vector @@ normalized_query.value
                )
                SELECT chunk_id, source_id, source_url, source_title,
                       publisher, reference_period, geographic_scope,
                       section, content, rank
                FROM ranked_chunks
                WHERE source_position = 1
                ORDER BY rank DESC, source_id
                LIMIT :limit
                """
            ),
            {"query": expanded_query, "limit": bounded_limit},
        )
        results = [dict(row) for row in rows.mappings().all()]
    metrics.increment(
        "assistant_rag_retrievals_total",
        status="hit" if results else "empty",
    )
    metrics.observe("assistant_rag_retrieval_duration_seconds", monotonic() - started)
    metrics.observe("assistant_rag_retrieval_results", len(results))
    return results


def record_sql_execution(engine: Engine, execution: dict) -> None:
    """Persist a bounded audit record without connection credentials."""
    allowed = {
        "execution_id",
        "request_id",
        "actor_id",
        "question",
        "interpretation_json",
        "schema_version",
        "generated_sql",
        "validation_status",
        "validation_error",
        "duration_ms",
        "row_count",
        "plan_cost",
        "prompt_version",
        "model_version",
    }
    record = {key: execution.get(key) for key in allowed}
    record["question"] = str(record["question"] or "")[:2_000]
    record["generated_sql"] = str(record["generated_sql"] or "")[:10_000]
    if record["validation_error"] is not None:
        record["validation_error"] = str(record["validation_error"])[:512]
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO assistant.sql_executions (
                    execution_id, request_id, actor_id, question,
                    interpretation_json, schema_version, generated_sql,
                    validation_status, validation_error, duration_ms,
                    row_count, plan_cost, prompt_version, model_version
                ) VALUES (
                    :execution_id, :request_id, :actor_id, :question,
                    :interpretation_json, :schema_version, :generated_sql,
                    :validation_status, :validation_error, :duration_ms,
                    :row_count, :plan_cost, :prompt_version, :model_version
                )
                """
            ),
            record,
        )


def _expand_business_query(query: str) -> str:
    normalized = query.casefold()
    expansions = {
        "inflation": "ipc indice prix consommation",
        "chômage": "bit population active",
        "chomage": "bit population active",
        "pauvreté": "niveau vie seuil",
        "pauvrete": "niveau vie seuil",
        "surendettement": "dossiers dettes ménages",
    }
    added = [
        terms for keyword, terms in expansions.items() if keyword in normalized
    ]
    return " ".join((query, *added))


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
