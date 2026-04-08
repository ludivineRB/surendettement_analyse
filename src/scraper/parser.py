"""Parsing helpers for extracting links and metadata from HTML pages."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import urldefrag, urljoin, urlparse

from bs4 import BeautifulSoup

YEAR_PATTERN = re.compile(r"(19|20)\d{2}")

# Small seed list; fallback remains generic and based on keyword matching.
REGION_HINTS = [
    "ile-de-france",
    "auvergne-rhone-alpes",
    "bourgogne-franche-comte",
    "bretagne",
    "centre-val-de-loire",
    "corse",
    "grand-est",
    "hauts-de-france",
    "normandie",
    "nouvelle-aquitaine",
    "occitanie",
    "pays-de-la-loire",
    "provence-alpes-cote-dazur",
    "guadeloupe",
    "martinique",
    "guyane",
    "la-reunion",
    "mayotte",
]


@dataclass(slots=True)
class ParsedLink:
    """Structured representation of a discovered link."""

    url: str
    text: str
    is_file: bool
    extension: str
    relevance_score: int
    year: Optional[int]
    region: Optional[str]
    dataset_type: str


def normalize_url(base_url: str, href: str) -> str:
    """Build an absolute URL from any href and remove fragments."""
    absolute_url = urljoin(base_url, href.strip())
    normalized, _ = urldefrag(absolute_url)
    return normalized


def is_http_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"}


def extract_extension(url: str) -> str:
    path = urlparse(url).path.lower()
    dot_index = path.rfind(".")
    if dot_index == -1:
        return ""
    return path[dot_index:]


def infer_year(*parts: str) -> Optional[int]:
    haystack = " ".join(parts)
    match = YEAR_PATTERN.search(haystack)
    if not match:
        return None
    return int(match.group(0))


def infer_region(*parts: str) -> Optional[str]:
    haystack = " ".join(parts).lower()
    for region_hint in REGION_HINTS:
        if region_hint in haystack:
            return region_hint
    return None


def infer_dataset_type(*parts: str) -> str:
    haystack = " ".join(parts).lower()
    if "typologie" in haystack:
        return "typologie"
    if "serie" in haystack or "série" in haystack:
        return "series_annuelles"
    if "statistique" in haystack:
        return "statistiques"
    if "surendettement" in haystack:
        return "surendettement"
    return "unknown"


def relevance_score(*parts: str, keywords: List[str]) -> int:
    haystack = " ".join(parts).lower()
    return sum(1 for kw in keywords if kw.lower() in haystack)


def parse_page_links(
    html: str,
    base_url: str,
    keywords: List[str],
    supported_extensions: List[str],
) -> List[ParsedLink]:
    """Parse all anchor links and infer metadata."""
    soup = BeautifulSoup(html, "lxml")
    links: List[ParsedLink] = []
    seen_urls: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "").strip()
        if not href:
            continue

        url = normalize_url(base_url, href)
        if not is_http_url(url) or url in seen_urls:
            continue

        seen_urls.add(url)
        text = " ".join(anchor.stripped_strings)
        extension = extract_extension(url)
        is_file = extension in {ext.lower() for ext in supported_extensions}

        link = ParsedLink(
            url=url,
            text=text,
            is_file=is_file,
            extension=extension,
            relevance_score=relevance_score(text, url, keywords=keywords),
            year=infer_year(text, url),
            region=infer_region(text, url),
            dataset_type=infer_dataset_type(text, url),
        )
        links.append(link)

    return links

