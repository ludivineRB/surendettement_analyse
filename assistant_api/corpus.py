"""Validation of the curated business-source registry."""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field


_OFFICIAL_HOSTS = {"www.banque-france.fr", "www.insee.fr"}


class CorpusRegistryError(ValueError):
    """Raised when a source registry is unsafe or ambiguous."""


class CorpusSource(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9-]+$")
    publisher: Literal["Banque de France", "Insee"]
    title: str = Field(min_length=5)
    url: str
    document_type: str = Field(min_length=3)
    published_at: date
    reference_period: str = Field(min_length=4)
    geographic_scope: str = Field(min_length=3)
    topics: list[str] = Field(min_length=1)
    usage: Literal["documents", "hybrid"]
    reviewed_at: date
    normalized_characters: int = Field(ge=50)
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class CorpusRegistry(BaseModel):
    schema_version: Literal["1.0"]
    review_status: Literal["content_reviewed"]
    sources: list[CorpusSource] = Field(min_length=1)


def load_registry(path: Path) -> CorpusRegistry:
    registry = CorpusRegistry.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    ids = [source.id for source in registry.sources]
    urls = [source.url for source in registry.sources]
    if len(ids) != len(set(ids)) or len(urls) != len(set(urls)):
        raise CorpusRegistryError("Source identifiers and URLs must be unique")
    invalid_hosts = {
        urlparse(source.url).hostname
        for source in registry.sources
        if urlparse(source.url).hostname not in _OFFICIAL_HOSTS
    }
    if invalid_hosts:
        raise CorpusRegistryError(
            f"Unofficial source hosts: {', '.join(sorted(invalid_hosts))}"
        )
    return registry


def default_registry_path() -> Path:
    return Path(__file__).with_name("corpus_registry.json")
