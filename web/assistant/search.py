"""PostgreSQL full-text search over the latest approved document versions."""

from __future__ import annotations

from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db.models import OuterRef, Subquery

from web.assistant.models import RagChunk, RagDocumentVersion


def lexical_search(query: str, *, limit: int = 10) -> list[dict]:
    query = query.strip()
    if not query:
        return []
    limit = max(1, min(limit, 50))
    latest_version = (
        RagDocumentVersion.objects.filter(
            document_id=OuterRef("document_version__document_id")
        )
        .order_by("-indexed_at", "-id")
        .values("id")[:1]
    )
    search_query = SearchQuery(query, config="french", search_type="websearch")
    chunks = (
        RagChunk.objects.filter(
            document_version__document__is_active=True,
            document_version_id=Subquery(latest_version),
        )
        .annotate(rank=SearchRank("search_vector", search_query))
        .filter(rank__gt=0)
        .select_related("document_version__document__source")
        .order_by("-rank", "id")[:limit]
    )
    return [
        {
            "chunk_id": chunk.id,
            "rank": float(chunk.rank),
            "title": chunk.title,
            "section": chunk.section,
            "content": chunk.content,
            "document": chunk.document_version.document.title,
            "document_slug": chunk.document_version.document.slug,
            "document_type": chunk.document_version.document.document_type,
            "version": chunk.document_version.version_label,
            "source_path": chunk.document_version.source_path,
            "source_url": (
                chunk.source_url
                or chunk.document_version.document.source_url
            ),
            "page_number": chunk.page_number,
            "territory": chunk.territory,
            "reference_period": chunk.reference_period,
            "indicator_code": chunk.indicator_code,
            "content_sha256": chunk.content_sha256,
        }
        for chunk in chunks
    ]
