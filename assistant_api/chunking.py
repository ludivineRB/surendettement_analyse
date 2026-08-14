"""Heading-aware chunks with stable business provenance."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from assistant_api.corpus import CorpusSource
from assistant_api.ingestion import FetchedDocument


@dataclass(frozen=True)
class CorpusChunk:
    chunk_id: str
    source_id: str
    source_url: str
    source_title: str
    publisher: str
    reference_period: str
    geographic_scope: str
    source_sha256: str
    section: str
    ordinal: int
    content: str
    content_sha256: str


def chunk_document(
    source: CorpusSource,
    document: FetchedDocument,
    *,
    max_characters: int = 1_500,
) -> list[CorpusChunk]:
    if max_characters < 300:
        raise ValueError("max_characters must be at least 300")
    sections = _split_sections(document.content, source.title)
    pieces: list[tuple[str, str]] = []
    for section, paragraphs in sections:
        current: list[str] = []
        current_length = 0
        for paragraph in paragraphs:
            if current and current_length + len(paragraph) + 2 > max_characters:
                pieces.append((section, "\n\n".join(current)))
                current = []
                current_length = 0
            current.append(paragraph)
            current_length += len(paragraph) + 2
        if current:
            pieces.append((section, "\n\n".join(current)))

    chunks: list[CorpusChunk] = []
    for ordinal, (section, content) in enumerate(pieces):
        content_sha = sha256(content.encode("utf-8")).hexdigest()
        stable_key = f"{source.id}:{ordinal}:{content_sha}"
        chunks.append(
            CorpusChunk(
                chunk_id=sha256(stable_key.encode("utf-8")).hexdigest(),
                source_id=source.id,
                source_url=source.url,
                source_title=source.title,
                publisher=source.publisher,
                reference_period=source.reference_period,
                geographic_scope=source.geographic_scope,
                source_sha256=document.content_sha256,
                section=section,
                ordinal=ordinal,
                content=content,
                content_sha256=content_sha,
            )
        )
    return chunks


def _split_sections(
    content: str,
    default_title: str,
) -> list[tuple[str, list[str]]]:
    sections: list[tuple[str, list[str]]] = []
    section = default_title
    paragraphs: list[str] = []
    for paragraph in content.split("\n\n"):
        if paragraph.startswith("#"):
            if paragraphs:
                sections.append((section, paragraphs))
                paragraphs = []
            section = paragraph.lstrip("# ").strip()
        elif paragraph.strip():
            paragraphs.append(paragraph.strip())
    if paragraphs:
        sections.append((section, paragraphs))
    return sections
