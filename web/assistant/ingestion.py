"""Approved-manifest ingestion for the documentary corpus."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from django.contrib.postgres.search import SearchVector
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from web.assistant.chunking import (
    CHUNKING_ALGORITHM_VERSION,
    chunk_markdown,
)
from web.assistant.models import (
    RagChunk,
    RagDocument,
    RagDocumentVersion,
    RagIndexRun,
    RagSource,
)


class CorpusIngestionError(ValueError):
    """Raised when a manifest entry is unsafe or incomplete."""


def ingest_manifest(manifest_path: Path, project_root: Path) -> RagIndexRun:
    manifest_path = manifest_path.resolve()
    project_root = project_root.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    algorithm = manifest.get("chunking_algorithm_version")
    if algorithm != CHUNKING_ALGORITHM_VERSION:
        raise CorpusIngestionError(
            f"Unsupported chunking algorithm: {algorithm}"
        )
    documents = manifest.get("documents")
    if not isinstance(documents, list) or not documents:
        raise CorpusIngestionError("Manifest documents must be a non-empty list")

    run = RagIndexRun.objects.create(
        manifest_path=str(manifest_path.relative_to(project_root)),
        chunking_algorithm_version=algorithm,
    )
    try:
        with transaction.atomic():
            for entry in documents:
                _ingest_entry(entry, project_root, run)
            run.status = RagIndexRun.Status.SUCCESS
            run.finished_at = timezone.now()
            run.save()
    except Exception as exc:
        run.status = RagIndexRun.Status.FAILED
        run.finished_at = timezone.now()
        run.error_message = str(exc)[:4000]
        run.save(
            update_fields=("status", "finished_at", "error_message")
        )
        raise
    return run


def _ingest_entry(entry: dict, project_root: Path, run: RagIndexRun) -> None:
    if entry.get("approved") is not True:
        raise CorpusIngestionError(
            f"Document is not approved: {entry.get('path', '<missing>')}"
        )
    required = (
        "path",
        "slug",
        "title",
        "document_type",
        "version_label",
        "approved_at",
        "source",
    )
    missing = [field for field in required if not entry.get(field)]
    if missing:
        raise CorpusIngestionError(
            f"Manifest entry is missing: {', '.join(missing)}"
        )

    source_path = (project_root / entry["path"]).resolve()
    if project_root not in source_path.parents:
        raise CorpusIngestionError("Document path escapes the project root")
    if source_path.suffix.lower() not in {".md", ".txt"}:
        raise CorpusIngestionError("Only approved Markdown or text is accepted")
    if not source_path.is_file():
        raise CorpusIngestionError(f"Document does not exist: {entry['path']}")

    approved_at = parse_datetime(entry["approved_at"])
    if approved_at is None:
        raise CorpusIngestionError("approved_at must be an ISO-8601 datetime")
    if timezone.is_naive(approved_at):
        approved_at = timezone.make_aware(approved_at)

    text = source_path.read_text(encoding="utf-8")
    content_sha = sha256(text.encode("utf-8")).hexdigest()
    source_data = entry["source"]
    source, _ = RagSource.objects.get_or_create(
        name=source_data["name"],
        defaults={
            "publisher": source_data.get("publisher", ""),
            "base_url": source_data.get("base_url", ""),
        },
    )
    document, created = RagDocument.objects.get_or_create(
        slug=entry["slug"],
        defaults={
            "source": source,
            "title": entry["title"],
            "document_type": entry["document_type"],
            "source_url": entry.get("source_url", ""),
            "metadata": entry.get("metadata", {}),
        },
    )
    if created:
        run.documents_created += 1
    existing = document.versions.filter(sha256=content_sha).first()
    if existing:
        run.documents_skipped += 1
        run.save()
        return

    chunks = chunk_markdown(text, document_title=entry["title"])
    if not chunks:
        raise CorpusIngestionError(f"Document is empty: {entry['path']}")
    version = RagDocumentVersion.objects.create(
        document=document,
        version_label=entry["version_label"],
        source_path=entry["path"],
        sha256=content_sha,
        approved_at=approved_at,
        chunking_algorithm_version=CHUNKING_ALGORITHM_VERSION,
    )
    chunk_metadata = entry.get("chunk_metadata", {})
    RagChunk.objects.bulk_create(
        [
            RagChunk(
                document_version=version,
                ordinal=chunk.ordinal,
                title=chunk.title,
                section=chunk.section,
                content=chunk.content,
                content_sha256=chunk.sha256,
                page_number=chunk_metadata.get("page_number"),
                territory=chunk_metadata.get("territory", ""),
                reference_period=chunk_metadata.get("reference_period", ""),
                indicator_code=chunk_metadata.get("indicator_code", ""),
                source_url=entry.get("source_url", ""),
            )
            for chunk in chunks
        ]
    )
    version.chunks.update(
        search_vector=(
            SearchVector("title", weight="A", config="french")
            + SearchVector("section", weight="A", config="french")
            + SearchVector("content", weight="B", config="french")
        )
    )
    run.versions_created += 1
    run.chunks_created += len(chunks)
    run.save()
