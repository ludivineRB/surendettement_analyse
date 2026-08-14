"""Controlled retrieval and normalization of approved HTML sources."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import re

from bs4 import BeautifulSoup
import requests

from assistant_api.corpus import CorpusSource


_MAX_SOURCE_BYTES = 2_000_000
_SPACE = re.compile(r"\s+")


class SourceRetrievalError(RuntimeError):
    """Raised when approved content cannot be retrieved safely."""


class SourceRevisionChanged(SourceRetrievalError):
    """Raised when a reviewed official page has changed."""


@dataclass(frozen=True)
class FetchedDocument:
    source_id: str
    source_url: str
    title: str
    content: str
    content_sha256: str


def fetch_source(source: CorpusSource) -> FetchedDocument:
    try:
        response = requests.get(
            source.url,
            headers={"User-Agent": "surendettement-analyse-corpus/1.0"},
            timeout=15,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise SourceRetrievalError(
            f"Source unavailable: {source.id}"
        ) from exc
    content_type = response.headers.get("Content-Type", "").lower()
    if "text/html" not in content_type:
        raise SourceRetrievalError(f"Unsupported content type: {source.id}")
    if len(response.content) > _MAX_SOURCE_BYTES:
        raise SourceRetrievalError(f"Source is too large: {source.id}")

    content = _extract_main_text(response.content)
    minimum_length = 50 if source.document_type == "definition" else 200
    if len(content) < minimum_length:
        raise SourceRetrievalError(f"Source content is incomplete: {source.id}")
    return FetchedDocument(
        source_id=source.id,
        source_url=source.url,
        title=source.title,
        content=content,
        content_sha256=sha256(content.encode("utf-8")).hexdigest(),
    )


def verify_reviewed_revision(
    source: CorpusSource,
    document: FetchedDocument,
) -> None:
    if (
        document.content_sha256 != source.content_sha256
        or len(document.content) != source.normalized_characters
    ):
        raise SourceRevisionChanged(
            f"Reviewed source changed and must be approved again: {source.id}"
        )


def _extract_main_text(raw_html: bytes) -> str:
    soup = BeautifulSoup(raw_html, "html.parser")
    main = soup.find("main")
    if main is None:
        raise SourceRetrievalError("HTML source has no main content")
    for unwanted in main.select("nav, script, style, form, footer, aside"):
        unwanted.decompose()
    lines: list[str] = []
    for element in main.find_all(["h1", "h2", "h3", "p", "li"]):
        text = _SPACE.sub(" ", element.get_text(" ", strip=True)).strip()
        if not text:
            continue
        prefix = {
            "h1": "# ",
            "h2": "## ",
            "h3": "### ",
            "li": "- ",
        }.get(element.name, "")
        lines.append(f"{prefix}{text}")
    return "\n\n".join(lines)
