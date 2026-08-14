"""Prepare a fully reviewed corpus before any database mutation."""

from __future__ import annotations

from collections.abc import Callable

from assistant_api.chunking import CorpusChunk, chunk_document
from assistant_api.corpus import CorpusRegistry, CorpusSource
from assistant_api.ingestion import (
    FetchedDocument,
    fetch_source,
    verify_reviewed_revision,
)


SourceFetcher = Callable[[CorpusSource], FetchedDocument]


def prepare_registry_chunks(
    registry: CorpusRegistry,
    *,
    fetcher: SourceFetcher = fetch_source,
) -> list[CorpusChunk]:
    reviewed_documents: list[tuple[CorpusSource, FetchedDocument]] = []
    for source in registry.sources:
        document = fetcher(source)
        verify_reviewed_revision(source, document)
        reviewed_documents.append((source, document))

    chunks: list[CorpusChunk] = []
    for source, document in reviewed_documents:
        chunks.extend(chunk_document(source, document))
    return chunks
