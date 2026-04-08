"""File downloader for discovered datasets."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, List, Optional
from urllib.parse import urlparse, urlunparse

import requests

from src.scraper.parser import ParsedLink, infer_dataset_type, infer_year
from src.utils.config import PipelineConfig
from src.utils.logger import get_logger

SAFE_TOKEN = re.compile(r"[^a-z0-9_]+")


def _slugify(value: str, default: str = "unknown") -> str:
    value = value.lower().replace("-", "_")
    value = SAFE_TOKEN.sub("_", value).strip("_")
    return value or default


class FileDownloader:
    """Download discovered files to raw storage with a deterministic naming convention."""

    def __init__(self, config: Optional[PipelineConfig] = None):
        self.config = config or PipelineConfig.from_env()
        self.logger = get_logger(self.__class__.__name__)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.config.user_agent})
        self.output_dir = self.config.output_raw_dir

    def build_filename(self, link: ParsedLink) -> str:
        year = str(link.year or infer_year(link.url) or "unknown")
        dataset_type = _slugify(link.dataset_type or infer_dataset_type(link.text, link.url))
        ext = link.extension if link.extension else Path(urlparse(link.url).path).suffix.lower()
        ext = ext if ext in {".xlsx", ".csv", ".pdf"} else ".bin"
        return f"bdf_{year}_{dataset_type}{ext}"

    def _ensure_unique_path(self, desired_name: str) -> Path:
        path = self.output_dir / desired_name
        if not path.exists():
            return path

        stem = path.stem
        suffix = path.suffix
        counter = 1
        while True:
            candidate = self.output_dir / f"{stem}_{counter}{suffix}"
            if not candidate.exists():
                return candidate
            counter += 1

    def download_file(self, link: ParsedLink) -> Optional[Path]:
        """Download one file and return local path or None on failure."""
        target_path = self._ensure_unique_path(self.build_filename(link))
        errors: list[str] = []
        for candidate_url in self._candidate_urls(link.url):
            try:
                with self.session.get(candidate_url, stream=True, timeout=self.config.timeout_seconds) as response:
                    response.raise_for_status()
                    with target_path.open("wb") as handle:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                handle.write(chunk)
                self.logger.info("Downloaded %s -> %s", candidate_url, target_path)
                return target_path
            except requests.RequestException as exc:
                errors.append(f"{candidate_url} => {exc}")

        self.logger.warning("Download failed for %s: %s", link.url, " | ".join(errors))
        if target_path.exists():
            target_path.unlink(missing_ok=True)
        return None

    def _candidate_urls(self, url: str) -> List[str]:
        """Return primary URL plus DNS fallback variants."""
        candidates = [url]
        parsed = urlparse(url)
        if parsed.netloc == "www.espaces2.banque-france.fr":
            fallback = parsed._replace(netloc="espaces2.banque-france.fr")
            candidates.append(urlunparse(fallback))
        return candidates

    def download_all(self, links: Iterable[ParsedLink]) -> List[Path]:
        """Download all candidate files and return successful local paths."""
        downloaded: List[Path] = []
        for link in links:
            path = self.download_file(link)
            if path:
                downloaded.append(path)
        return downloaded
