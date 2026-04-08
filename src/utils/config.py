"""Centralized runtime configuration for the data pipeline."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List


def _split_csv(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(slots=True)
class PipelineConfig:
    """Configuration container with environment-variable overrides."""

    base_url: str = os.getenv("BDF_BASE_URL", "https://www.banque-france.fr/fr")
    allowed_domains: List[str] = field(
        default_factory=lambda: _split_csv(
            os.getenv("BDF_ALLOWED_DOMAINS", "banque-france.fr,www.banque-france.fr")
        )
    )
    keywords: List[str] = field(
        default_factory=lambda: _split_csv(
            os.getenv(
                "BDF_KEYWORDS",
                "surendettement,statistiques,typologie,series annuelles,séries annuelles",
            )
        )
    )
    file_extensions: List[str] = field(
        default_factory=lambda: _split_csv(os.getenv("BDF_FILE_EXTENSIONS", ".xlsx,.csv,.pdf"))
    )
    start_urls: List[str] = field(default_factory=lambda: _split_csv(os.getenv("BDF_START_URLS", "")))
    timeout_seconds: int = int(os.getenv("BDF_TIMEOUT_SECONDS", "20"))
    max_depth: int = int(os.getenv("BDF_MAX_DEPTH", "3"))
    max_pages: int = int(os.getenv("BDF_MAX_PAGES", "500"))
    user_agent: str = os.getenv(
        "BDF_USER_AGENT",
        "Mozilla/5.0 (compatible; SurendettementDataPipeline/1.0; +https://www.banque-france.fr/fr)",
    )
    output_raw_dir: Path = Path(os.getenv("BDF_RAW_DIR", "data/raw"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    def __post_init__(self) -> None:
        if not self.start_urls:
            self.start_urls = [self.base_url]
        self.output_raw_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env(cls) -> "PipelineConfig":
        return cls()

    def is_allowed_domain(self, domain: str) -> bool:
        domain = domain.lower()
        return any(domain == allowed or domain.endswith(f".{allowed}") for allowed in self.allowed_domains)

    def is_supported_extension(self, extension: str) -> bool:
        return extension.lower() in {ext.lower() for ext in self.file_extensions}

    def keyword_iter(self) -> Iterable[str]:
        return (keyword.lower() for keyword in self.keywords if keyword.strip())
