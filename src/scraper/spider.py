"""Crawler responsible for discovering pages and downloadable datasets."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, List, Optional, Set, Tuple
from urllib.parse import urlparse

import requests

from src.scraper.parser import ParsedLink, parse_page_links
from src.utils.config import PipelineConfig
from src.utils.logger import get_logger


@dataclass(slots=True)
class CrawlResult:
    """Result object grouping discovered pages and downloadable resources."""

    pages: List[str]
    files: List[ParsedLink]


class BanqueFranceSpider:
    """Domain-limited BFS spider tuned for surendettement resources."""

    def __init__(self, config: Optional[PipelineConfig] = None):
        self.config = config or PipelineConfig.from_env()
        self.logger = get_logger(self.__class__.__name__)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.config.user_agent})
        self._supported_extensions = [ext.lower() for ext in self.config.file_extensions]

    def _is_allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return False
        return self.config.is_allowed_domain(parsed.netloc)

    def _fetch_page(self, url: str) -> Optional[str]:
        try:
            response = self.session.get(url, timeout=self.config.timeout_seconds)
            response.raise_for_status()
        except requests.RequestException as exc:
            self.logger.warning("Failed to fetch %s: %s", url, exc)
            return None

        content_type = response.headers.get("Content-Type", "").lower()
        if "text/html" not in content_type:
            return None

        return response.text

    def _relevance_from_text(self, text: str, keywords: List[str]) -> int:
        lower = text.lower()
        return sum(1 for keyword in keywords if keyword in lower)

    def crawl(self) -> CrawlResult:
        """Run recursive crawl from configured start URLs."""
        queue: Deque[Tuple[str, int, bool]] = deque()
        visited_pages: Set[str] = set()
        discovered_files: dict[str, ParsedLink] = {}
        discovered_pages: Set[str] = set()
        keywords = list(self.config.keyword_iter())

        seeded_urls: Set[str] = set()
        for start_url in self.config.start_urls:
            if self._is_allowed(start_url):
                is_relevant_seed = self._relevance_from_text(start_url, keywords) > 0
                queue.append((start_url, 0, is_relevant_seed))
                seeded_urls.add(start_url)

        # Safety fallback: if configured seeds are stale (404) or too narrow,
        # always include the main base URL as an additional entry point.
        if self._is_allowed(self.config.base_url) and self.config.base_url not in seeded_urls:
            queue.append((self.config.base_url, 0, True))

        crawled_count = 0

        while queue and crawled_count < self.config.max_pages:
            current_url, depth, is_relevant_path = queue.popleft()
            if current_url in visited_pages or depth > self.config.max_depth:
                continue

            visited_pages.add(current_url)
            html = self._fetch_page(current_url)
            if html is None:
                continue

            crawled_count += 1
            discovered_pages.add(current_url)
            self.logger.info("Crawled (%d/%d): %s", crawled_count, self.config.max_pages, current_url)

            links = parse_page_links(
                html=html,
                base_url=current_url,
                keywords=keywords,
                supported_extensions=self._supported_extensions,
            )

            for link in links:
                if not self._is_allowed(link.url):
                    continue

                if link.is_file:
                    # Keep only files found on relevant paths or directly relevant links.
                    if is_relevant_path or link.relevance_score > 0:
                        discovered_files.setdefault(link.url, link)
                    continue

                next_relevant = is_relevant_path or link.relevance_score > 0
                # We allow one "bridge" level even if low relevance, to jump from generic pages.
                if depth < self.config.max_depth and (next_relevant or depth < 1):
                    queue.append((link.url, depth + 1, next_relevant))

        return CrawlResult(
            pages=sorted(discovered_pages),
            files=sorted(discovered_files.values(), key=lambda item: item.url),
        )
