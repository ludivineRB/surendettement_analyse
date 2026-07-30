"""Deterministic Markdown chunking with section provenance."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import re

CHUNKING_ALGORITHM_VERSION = "markdown-sections-v1"
MAX_CHUNK_CHARACTERS = 1800
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


@dataclass(frozen=True, slots=True)
class Chunk:
    ordinal: int
    title: str
    section: str
    content: str
    sha256: str


def chunk_markdown(
    text: str,
    *,
    document_title: str,
    maximum_characters: int = MAX_CHUNK_CHARACTERS,
) -> list[Chunk]:
    if maximum_characters < 200:
        raise ValueError("maximum_characters must be at least 200")
    sections = _sections(text, document_title)
    chunks = []
    for title, section_path, content in sections:
        for piece in _split_content(content, maximum_characters):
            normalized = piece.strip()
            if not normalized:
                continue
            chunks.append(
                Chunk(
                    ordinal=len(chunks),
                    title=title,
                    section=section_path,
                    content=normalized,
                    sha256=sha256(normalized.encode("utf-8")).hexdigest(),
                )
            )
    return chunks


def _sections(text: str, document_title: str):
    hierarchy: list[str] = []
    current_title = document_title
    current_path = document_title
    lines: list[str] = []
    output = []

    def flush():
        content = "\n".join(lines).strip()
        if content:
            output.append((current_title, current_path, content))

    for line in text.splitlines():
        match = HEADING_RE.match(line)
        if not match:
            lines.append(line)
            continue
        flush()
        lines.clear()
        level = len(match.group(1))
        heading = match.group(2).strip()
        del hierarchy[level - 1 :]
        while len(hierarchy) < level - 1:
            hierarchy.append(document_title)
        hierarchy.append(heading)
        current_title = heading
        current_path = " > ".join(hierarchy)
    flush()
    return output


def _split_content(content: str, maximum_characters: int):
    paragraphs = re.split(r"\n\s*\n", content)
    buffer = ""
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(paragraph) > maximum_characters:
            if buffer:
                yield buffer
                buffer = ""
            for start in range(0, len(paragraph), maximum_characters):
                yield paragraph[start : start + maximum_characters]
            continue
        candidate = f"{buffer}\n\n{paragraph}".strip()
        if buffer and len(candidate) > maximum_characters:
            yield buffer
            buffer = paragraph
        else:
            buffer = candidate
    if buffer:
        yield buffer
