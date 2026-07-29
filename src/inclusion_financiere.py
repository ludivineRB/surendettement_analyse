"""Pipeline for Banque de France regional financial-inclusion barometers."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import tempfile
import time
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urldefrag, urljoin, urlparse

import pdfplumber
import requests
from bs4 import BeautifulSoup
from sqlalchemy import select

from src.storage.database import get_session_factory, init_db
from src.storage.models import InclusionIndicator, InclusionObservation, InclusionSourceDocument
from src.utils.config import PipelineConfig
from src.utils.logger import configure_logging, get_logger

EXTRACTOR_VERSION = "inclusion-financiere-v3"
PUBLICATION_TYPE = "barometre_mensuel_inclusion_financiere"
PUBLISHER = "Banque de France"
DEFAULT_LISTING_URL = (
    "https://www.banque-france.fr/fr/publications-et-statistiques/statistiques"
    "?keywords=barom%C3%A8tre%20mensuel%20de%20l%27inclusion%20financi%C3%A8re"
)
DEFAULT_STORAGE_ROOT = Path("data/raw/banque_france/inclusion_financiere")
DEFAULT_JSONL = Path("data/processed/inclusion_financiere_observations.jsonl")
MIN_PDF_BYTES = 512
MAX_PDF_BYTES = 25 * 1024 * 1024

MONTHS = {
    "janvier": "01",
    "fevrier": "02",
    "février": "02",
    "mars": "03",
    "avril": "04",
    "mai": "05",
    "juin": "06",
    "juillet": "07",
    "aout": "08",
    "août": "08",
    "septembre": "09",
    "octobre": "10",
    "novembre": "11",
    "decembre": "12",
    "décembre": "12",
}
URL_MONTH_SLUGS = {
    "01": "janvier",
    "02": "fevrier",
    "03": "mars",
    "04": "avril",
    "05": "mai",
    "06": "juin",
    "07": "juillet",
    "08": "aout",
    "09": "septembre",
    "10": "octobre",
    "11": "novembre",
    "12": "decembre",
}

REGIONS = {
    "auvergne-rhone-alpes": ("84", "Auvergne-Rhône-Alpes"),
    "bourgogne-franche-comte": ("27", "Bourgogne-Franche-Comté"),
    "bretagne": ("53", "Bretagne"),
    "centre-val-de-loire": ("24", "Centre-Val de Loire"),
    "corse": ("94", "Corse"),
    "grand-est": ("44", "Grand Est"),
    "hauts-de-france": ("32", "Hauts-de-France"),
    "ile-de-france": ("11", "Île-de-France"),
    "normandie": ("28", "Normandie"),
    "nouvelle-aquitaine": ("75", "Nouvelle-Aquitaine"),
    "occitanie": ("76", "Occitanie"),
    "pays-de-la-loire": ("52", "Pays de la Loire"),
    "provence-alpes-cote-dazur": ("93", "Provence-Alpes-Côte d’Azur"),
}

INDICATOR_PATTERNS = {
    "surendettement_dossiers_deposes": (
        "Dossiers de surendettement déposés",
        "dossiers",
        re.compile(
            r"Nombre\s+de\s+dossiers\s+d[ée]pos[ée]s[ \t]{2,}"
            r"(-?\d+(?:[ \u00a0]\d{3})*)[ \t]{2,}",
            re.I,
        ),
    ),
    "droit_compte_designations": (
        "Désignations au titre du droit au compte",
        "désignations",
        re.compile(
            r"banque\s+pour\s+l['’]ouverture\s+d['’]un[ \t]{2,}"
            r"(-?\d+(?:[ \u00a0]\d{3})*)[ \t]{2,}",
            re.I,
        ),
    ),
    "fcc_personnes_inscrites": (
        "Inscriptions de personnes au FCC",
        "inscriptions",
        re.compile(
            r"Inscription\s+des\s+personnes\s+au\s+FCC[ \t]{2,}"
            r"(-?\d+(?:[ \u00a0]\d{3})*)[ \t]{2,}",
            re.I,
        ),
    ),
}

PARTIAL_TEXT_PATTERNS = {
    "surendettement_dossiers_deposes": re.compile(
        r"Dossiers\s+de\s+surendettement\s+d[ée]pos[ée]s\s+"
        r"(-?\d+(?:[ \u00a0]\d{3})*)\b",
        re.I,
    ),
    "droit_compte_designations": re.compile(
        r"Droit\s+au\s+compte\s+(-?\d+(?:[ \u00a0]\d{3})*)\b",
        re.I,
    ),
}

# Corrections vérifiées de publications dont le slug ou la pièce jointe HTML
# est erroné sur le site source. Elles restent bornées à un territoire/période.
KNOWN_PUBLICATION_OVERRIDES = (
    {
        "page_url": (
            "https://www.banque-france.fr/fr/publications-et-statistiques/"
            "statistiques/barometre-mensuel-de-linclusion-financiere-"
            "grand-est-avril-2025-0"
        ),
        "title": (
            "Baromètre mensuel de l’inclusion financière : "
            "Grand Est - mai 2025"
        ),
        "region_code": "44",
        "region_name": "Grand Est",
        "region_slug": "grand-est",
        "reference_month": "05",
        "reference_year": 2025,
        "pdf_url": (
            "https://www.banque-france.fr/system/files/2025-06/"
            "BARO_REG_052025_Grand-Est.pdf"
        ),
        "pdf_filename": "BARO_REG_052025_Grand-Est.pdf",
        "publication_date": "2025-06-13",
    },
    {
        "page_url": (
            "https://www.banque-france.fr/fr/publications-et-statistiques/"
            "statistiques/barometre-mensuel-de-linclusion-financiere-"
            "centre-val-de-loire-mai-2026"
        ),
        "title": (
            "Baromètre mensuel de l’inclusion financière : "
            "Centre-Val-de-Loire - mai 2026"
        ),
        "region_code": "24",
        "region_name": "Centre-Val de Loire",
        "region_slug": "centre-val-de-loire",
        "reference_month": "05",
        "reference_year": 2026,
        "pdf_url": (
            "https://www.banque-france.fr/system/files/2026-06/"
            "BARO_REG_052026_Centre-Val%20de%20Loire.pdf"
        ),
        "pdf_filename": "BARO_REG_052026_Centre-Val de Loire.pdf",
        "publication_date": "2026-06-11",
    },
)


@dataclass(slots=True)
class PublicationMetadata:
    page_url: str
    title: str
    region_code: str
    region_name: str
    region_slug: str
    reference_month: str
    reference_year: int
    reference_period: str
    publication_date: Optional[str]
    updated_date: Optional[str]
    pdf_url: str
    pdf_filename: str
    announced_size: Optional[str]
    discovered_at: str
    last_checked_at: str


@dataclass(slots=True)
class DownloadedDocument:
    metadata: PublicationMetadata
    storage_path: Path
    pdf_sha256: str
    pdf_size_bytes: int
    http_etag: Optional[str]
    http_last_modified: Optional[str]
    downloaded_at: str
    unchanged: bool = False


@dataclass(slots=True)
class QualityReport:
    page_count: int = 0
    tables_detected: int = 0
    observations_extracted: int = 0
    rejected_values: int = 0
    fill_rate: float = 0.0
    method: str = "native_text"
    confidence_score: float = 0.0
    warnings: list[str] = field(default_factory=list)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.replace("’", "'"))
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")


def month_to_number(value: str) -> str:
    key = slugify(value).replace("-", "")
    for label, number in MONTHS.items():
        if slugify(label).replace("-", "") == key:
            return number
    raise ValueError(f"Unknown French month: {value}")


def parse_period(month: str, year: int | str) -> str:
    return f"{int(year):04d}-{month_to_number(month)}"


def parse_french_number(value: str) -> Optional[float]:
    clean = value.strip().lower().replace("\u00a0", "").replace(" ", "")
    if clean in {"", "-", "n.d.", "nd", "n.s.", "ns"}:
        return None
    negative = clean.startswith("(") and clean.endswith(")")
    clean = clean.strip("()").replace("%", "").replace(",", ".")
    try:
        number = float(clean)
    except ValueError:
        return None
    return -number if negative else number


def normalize_region(value: str) -> tuple[str, str, str]:
    slug = slugify(value)
    aliases = {
        "ile-de-france": "ile-de-france",
        "idf": "ile-de-france",
        "paca": "provence-alpes-cote-dazur",
        "provence-alpes-cote-d-azur": "provence-alpes-cote-dazur",
        "auvergne-rhone-alpes": "auvergne-rhone-alpes",
    }
    slug = aliases.get(slug, slug)
    if slug not in REGIONS:
        raise ValueError(f"Unknown region: {value}")
    code, label = REGIONS[slug]
    return code, label, slug


def idempotence_key(*parts: object) -> str:
    return hashlib.sha256("|".join(str(part or "") for part in parts).encode("utf-8")).hexdigest()


class InclusionFinancialPipeline:
    def __init__(
        self,
        config: Optional[PipelineConfig] = None,
        listing_url: str = DEFAULT_LISTING_URL,
        storage_root: Path = DEFAULT_STORAGE_ROOT,
        output_jsonl: Path = DEFAULT_JSONL,
        max_retries: int = 3,
        max_pdf_bytes: int = MAX_PDF_BYTES,
    ):
        self.config = config or PipelineConfig.from_env()
        self.listing_url = listing_url
        self.storage_root = storage_root
        self.output_jsonl = output_jsonl
        self.max_retries = max_retries
        self.max_pdf_bytes = max_pdf_bytes
        self.logger = get_logger("inclusion_financiere")
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.config.user_agent})

    def discover(
        self,
        from_period: str = "2024-01",
        to_period: Optional[str] = None,
        regions: Optional[Iterable[str]] = None,
    ) -> list[PublicationMetadata]:
        wanted_slugs = {normalize_region(region)[2] for region in regions} if regions else set(REGIONS)
        urls = self._discover_publication_urls(
            from_period=from_period,
            to_period=to_period,
            region_slugs=wanted_slugs,
        )
        metadata: list[PublicationMetadata] = []
        for override in KNOWN_PUBLICATION_OVERRIDES:
            period = (
                f"{override['reference_year']:04d}-"
                f"{override['reference_month']}"
            )
            if override["region_slug"] not in wanted_slugs:
                continue
            if period < from_period or (to_period and period > to_period):
                continue
            metadata.append(
                PublicationMetadata(
                    page_url=override["page_url"],
                    title=override["title"],
                    region_code=override["region_code"],
                    region_name=override["region_name"],
                    region_slug=override["region_slug"],
                    reference_month=override["reference_month"],
                    reference_year=override["reference_year"],
                    reference_period=period,
                    publication_date=override["publication_date"],
                    updated_date=override["publication_date"],
                    pdf_url=override["pdf_url"],
                    pdf_filename=override["pdf_filename"],
                    announced_size=None,
                    discovered_at=now_iso(),
                    last_checked_at=now_iso(),
                )
            )
        for url in urls:
            url_period = period_from_publication_url(url)
            if url_period and (url_period < from_period or (to_period and url_period > to_period)):
                continue
            try:
                html, final_url, _ = self._fetch_html(url)
                item = build_metadata(html, final_url)
                if item.region_slug not in wanted_slugs:
                    continue
                if item.reference_period < from_period or (to_period and item.reference_period > to_period):
                    continue
                metadata.append(item)
            except Exception as exc:
                self.logger.warning("stage=discover status=failed url=%s error=%s", url, exc)
        return sorted({item.page_url: item for item in metadata}.values(), key=lambda item: item.page_url)

    def _discover_publication_urls(self, from_period: str, to_period: Optional[str], region_slugs: set[str]) -> list[str]:
        urls: list[str] = []
        try:
            html, final_url, _ = self._fetch_html(self.listing_url)
            urls.extend(extract_publication_links(html, final_url))
        except Exception as exc:
            self.logger.warning("stage=discover_listing status=failed url=%s error=%s", self.listing_url, exc)

        urls.extend(self._discover_from_sitemap())
        if not urls:
            urls.extend(build_fallback_publication_urls(from_period, to_period, region_slugs))
        return sorted(set(urls))

    def _discover_from_sitemap(self) -> list[str]:
        sitemap_url = "https://www.banque-france.fr/sitemap.xml"
        try:
            response = self.session.get(sitemap_url, timeout=self.config.timeout_seconds)
            if response.status_code != 200:
                return []
        except requests.RequestException:
            return []
        return sorted(
            set(
                match.group(0)
                for match in re.finditer(r"https://www\.banque-france\.fr[^<]+barometre-mensuel-de-linclusion-financiere[^<]+", response.text)
            )
        )

    def _fetch_html(self, url: str) -> tuple[str, str, dict[str, str]]:
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.get(url, timeout=self.config.timeout_seconds)
                response.raise_for_status()
                if "text/html" not in response.headers.get("Content-Type", "text/html").lower():
                    raise ValueError("page HTML inaccessible")
                return response.text, response.url, dict(response.headers)
            except (requests.RequestException, ValueError) as exc:
                if (
                    isinstance(exc, requests.HTTPError)
                    and exc.response is not None
                    and 400 <= exc.response.status_code < 500
                    and exc.response.status_code not in {408, 429}
                ):
                    raise
                if attempt == self.max_retries:
                    raise
                self.logger.info("stage=fetch_html status=retry url=%s attempt=%s error=%s", url, attempt, exc)
                time.sleep(0.2 * (2 ** (attempt - 1)))
        raise RuntimeError("unreachable")

    def download(self, metadata: PublicationMetadata, force: bool = False, dry_run: bool = False) -> Optional[DownloadedDocument]:
        target_dir = self.storage_root / str(metadata.reference_year) / metadata.reference_month / metadata.region_slug
        if dry_run:
            return DownloadedDocument(metadata, target_dir / "dry-run.pdf", "", 0, None, None, now_iso(), unchanged=True)
        target_dir.mkdir(parents=True, exist_ok=True)
        headers: dict[str, str] = {}
        existing = self._find_known_document(metadata)
        if existing and not force:
            headers.update({k: v for k, v in {"If-None-Match": existing.http_etag, "If-Modified-Since": existing.http_last_modified}.items() if v})
        response = self._download_response(metadata.pdf_url, headers=headers)
        if response.status_code == 304 and existing:
            return DownloadedDocument(
                metadata, Path(existing.storage_path), existing.pdf_sha256, existing.pdf_size_bytes or 0,
                existing.http_etag, existing.http_last_modified, now_iso(), unchanged=True
            )
        data = response.content
        validate_pdf_response(response.status_code, response.headers.get("Content-Type", ""), data, self.max_pdf_bytes)
        sha256 = hashlib.sha256(data).hexdigest()
        final_path = target_dir / f"{sha256}.pdf"
        if final_path.exists() and not force:
            return DownloadedDocument(
                metadata, final_path, sha256, len(data), response.headers.get("ETag"),
                response.headers.get("Last-Modified"), now_iso(), unchanged=True
            )
        with tempfile.NamedTemporaryFile("wb", dir=target_dir, delete=False) as tmp:
            tmp.write(data)
            tmp_path = Path(tmp.name)
        tmp_path.replace(final_path)
        return DownloadedDocument(
            metadata, final_path, sha256, len(data), response.headers.get("ETag"),
            response.headers.get("Last-Modified"), now_iso(), unchanged=False
        )

    def _download_response(self, url: str, headers: dict[str, str]):
        parsed = urlparse(url)
        if not self.config.is_allowed_domain(parsed.netloc):
            raise ValueError(f"Unexpected PDF domain: {parsed.netloc}")
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.get(url, timeout=self.config.timeout_seconds, headers=headers)
                if response.status_code == 304:
                    return response
                response.raise_for_status()
                return response
            except requests.RequestException as exc:
                if attempt == self.max_retries:
                    raise
                self.logger.info("stage=download status=retry url=%s attempt=%s error=%s", url, attempt, exc)
                time.sleep(0.3 * (2 ** (attempt - 1)))
        raise RuntimeError("unreachable")

    def _find_known_document(self, metadata: PublicationMetadata) -> Optional[InclusionSourceDocument]:
        try:
            factory = get_session_factory()
            with factory() as session:
                return session.execute(
                    select(InclusionSourceDocument)
                    .where(InclusionSourceDocument.page_url == metadata.page_url)
                    .order_by(InclusionSourceDocument.id.desc())
                ).scalars().first()
        except Exception:
            return None

    def extract(self, document: DownloadedDocument) -> tuple[list[dict], QualityReport]:
        observations: list[dict] = []
        report = QualityReport()
        try:
            with pdfplumber.open(str(document.storage_path)) as pdf:
                report.page_count = len(pdf.pages)
                for page_number, page in enumerate(pdf.pages, start=1):
                    tables = page.extract_tables() or []
                    report.tables_detected += len(tables)
                    text = page.extract_text(layout=True) or ""
                    observations.extend(extract_observations_from_text(text, document, page_number))
        except Exception as exc:
            report.warnings.append(f"parsing_failed:{exc}")
            report.method = "failed"
        report.observations_extracted = len(observations)
        report.confidence_score = 0.9 if observations else 0.0
        report.fill_rate = 1.0 if observations else 0.0
        if report.page_count == 0:
            report.warnings.append("empty_or_unreadable_pdf")
        if not observations:
            report.warnings.append("anormally_empty_extraction")
        return observations, report

    def write_jsonl(self, documents: list[tuple[DownloadedDocument, list[dict], QualityReport]], dry_run: bool = False) -> int:
        if dry_run:
            return sum(len(rows) for _, rows, _ in documents)
        self.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        with self.output_jsonl.open("w", encoding="utf-8") as handle:
            for document, rows, report in documents:
                payload = build_intermediate_document(document, rows, report)
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
                count += len(rows)
        return count

    def load(self, documents: list[tuple[DownloadedDocument, list[dict], QualityReport]], dry_run: bool = False) -> tuple[int, int]:
        if dry_run:
            return 0, 0
        init_db()
        inserted_docs = 0
        inserted_obs = 0
        factory = get_session_factory()
        with factory() as session:
            ensure_indicators(session)
            for downloaded, rows, report in documents:
                status = "success" if rows and not report.warnings else "needs_review"
                source = session.execute(
                    select(InclusionSourceDocument).where(InclusionSourceDocument.pdf_sha256 == downloaded.pdf_sha256)
                ).scalars().first()
                if source is None:
                    source = InclusionSourceDocument(
                        source_name=PUBLISHER,
                        publication_type=PUBLICATION_TYPE,
                        region_code=downloaded.metadata.region_code,
                        region_name=downloaded.metadata.region_name,
                        reference_period=downloaded.metadata.reference_period,
                        publication_date=downloaded.metadata.publication_date,
                        updated_date=downloaded.metadata.updated_date,
                        page_url=downloaded.metadata.page_url,
                        pdf_url=downloaded.metadata.pdf_url,
                        pdf_filename=downloaded.metadata.pdf_filename,
                        pdf_sha256=downloaded.pdf_sha256,
                        pdf_size_bytes=downloaded.pdf_size_bytes,
                        storage_path=str(downloaded.storage_path),
                        http_etag=downloaded.http_etag,
                        http_last_modified=downloaded.http_last_modified,
                        downloaded_at=downloaded.downloaded_at,
                        extraction_status=status,
                        extractor_version=EXTRACTOR_VERSION,
                    )
                    session.add(source)
                    session.flush()
                    inserted_docs += 1
                for row in rows:
                    indicator = session.execute(
                        select(InclusionIndicator).where(InclusionIndicator.code == row["indicator_code"])
                    ).scalars().one()
                    exists = session.execute(
                        select(InclusionObservation.id).where(InclusionObservation.idempotence_key == row["idempotence_key"])
                    ).first()
                    if exists:
                        continue
                    session.add(InclusionObservation(source_document_id=source.id, indicator_id=indicator.id, **row))
                    inserted_obs += 1
            session.commit()
        return inserted_docs, inserted_obs

    def run(self, args) -> dict[str, int]:
        discovered = self.discover(args.from_period, args.to_period, args.regions)
        if args.command == "discover":
            return {
                "pages_discovered": len(discovered),
                "pdf_new": 0,
                "pdf_unchanged": 0,
                "failures": 0,
                "documents_extracted": 0,
                "observations_jsonl": 0,
                "observations_loaded": 0,
                "needs_review": 0,
            }
        processed = []
        failed = 0
        downloaded_count = 0
        skipped = 0
        for metadata in discovered:
            try:
                doc = self.download(metadata, force=args.force, dry_run=args.dry_run)
                if not doc:
                    failed += 1
                    continue
                downloaded_count += 0 if doc.unchanged else 1
                skipped += 1 if doc.unchanged else 0
                rows, report = self.extract(doc) if args.command in {"extract", "load", "run"} else ([], QualityReport())
                processed.append((doc, rows, report))
            except Exception as exc:
                failed += 1
                self.logger.warning("stage=document status=failed url=%s error=%s", metadata.page_url, exc)
        jsonl_rows = self.write_jsonl(processed, dry_run=args.dry_run) if args.command in {"extract", "load", "run"} else 0
        _, loaded = self.load(processed, dry_run=args.dry_run or args.no_load or args.command != "run")
        return {
            "pages_discovered": len(discovered),
            "pdf_new": downloaded_count,
            "pdf_unchanged": skipped,
            "failures": failed,
            "documents_extracted": sum(1 for _, rows, _ in processed if rows),
            "observations_jsonl": jsonl_rows,
            "observations_loaded": loaded,
            "needs_review": sum(1 for _, _, report in processed if report.warnings),
        }


def extract_publication_links(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    urls: list[str] = []
    for anchor in soup.find_all("a", href=True):
        text = " ".join(anchor.stripped_strings)
        url, _ = urldefrag(urljoin(base_url, anchor["href"].strip()))
        if is_publication_candidate(text, url):
            urls.append(url)
    urls.extend(urljoin(base_url, match.group(0).replace("\\/", "/")) for match in re.finditer(r"/fr/[^\"'<\s]*barometre-mensuel-de-linclusion-financiere[^\"'<\s]*", html))
    return sorted(set(urls))


def is_publication_candidate(text: str, url: str) -> bool:
    haystack = slugify(f"{text} {url}")
    return "barometre-mensuel-de-linclusion-financiere" in haystack


def build_fallback_publication_urls(
    from_period: str,
    to_period: Optional[str],
    region_slugs: Iterable[str],
) -> list[str]:
    end_period = to_period or datetime.now(timezone.utc).strftime("%Y-%m")
    urls: list[str] = []
    for period in iter_month_periods(from_period, end_period):
        year, month = period.split("-")
        month_slug = URL_MONTH_SLUGS[month]
        for region_slug in sorted(region_slugs):
            urls.append(
                "https://www.banque-france.fr/fr/publications-et-statistiques/statistiques/"
                f"barometre-mensuel-de-linclusion-financiere-{region_slug}-{month_slug}-{year}"
            )
    return urls


def iter_month_periods(from_period: str, to_period: str) -> list[str]:
    start_year, start_month = parse_iso_month(from_period)
    end_year, end_month = parse_iso_month(to_period)
    if (end_year, end_month) < (start_year, start_month):
        raise ValueError("--to must be greater than or equal to --from")
    periods: list[str] = []
    year = start_year
    month = start_month
    while (year, month) <= (end_year, end_month):
        periods.append(f"{year:04d}-{month:02d}")
        month += 1
        if month == 13:
            year += 1
            month = 1
    return periods


def parse_iso_month(value: str) -> tuple[int, int]:
    match = re.fullmatch(r"((?:19|20)\d{2})-(0[1-9]|1[0-2])", value)
    if not match:
        raise ValueError(f"Invalid period, expected YYYY-MM: {value}")
    return int(match.group(1)), int(match.group(2))


def period_from_publication_url(url: str) -> Optional[str]:
    match = re.search(
        rf"-(?P<month>{'|'.join(URL_MONTH_SLUGS.values())})-(?P<year>(?:19|20)\d{{2}})(?:[/?#]|$)",
        url,
        re.I,
    )
    if not match:
        return None
    return f"{int(match.group('year')):04d}-{month_to_number(match.group('month'))}"


def build_metadata(html: str, page_url: str) -> PublicationMetadata:
    soup = BeautifulSoup(html, "lxml")
    canonical = soup.find("link", rel=lambda value: value and "canonical" in value)
    page_url = urljoin(page_url, canonical["href"]) if canonical and canonical.get("href") else page_url
    title = _title_from_soup(soup)
    region_name, month_name, year = parse_title(title, page_url)
    region_code, official_region, region_slug = normalize_region(region_name)
    pdf_url, announced_size = extract_pdf_url(html, page_url)
    filename = Path(urlparse(pdf_url).path).name
    published = extract_date(soup, ("datePublished", "article:published_time", "publication_date"))
    updated = extract_date(soup, ("dateModified", "article:modified_time", "updated_time"))
    checked = now_iso()
    return PublicationMetadata(
        page_url=page_url,
        title=title,
        region_code=region_code,
        region_name=official_region,
        region_slug=region_slug,
        reference_month=month_to_number(month_name),
        reference_year=int(year),
        reference_period=parse_period(month_name, year),
        publication_date=published,
        updated_date=updated,
        pdf_url=pdf_url,
        pdf_filename=filename,
        announced_size=announced_size,
        discovered_at=checked,
        last_checked_at=checked,
    )


def _title_from_soup(soup: BeautifulSoup) -> str:
    h1 = soup.find("h1")
    if h1:
        return " ".join(h1.stripped_strings)
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    raise ValueError("missing title")


def parse_title(title: str, page_url: str) -> tuple[str, str, int]:
    pattern = re.compile(
        r"inclusion\s+financi[èe]re\s*:?\s*(?P<region>.+?)\s*[-–]\s*(?P<month>[A-Za-zéûôîàèùç]+)\s+(?P<year>(?:19|20)\d{2})",
        re.I,
    )
    match = pattern.search(title)
    if match:
        return match.group("region").strip(), match.group("month"), int(match.group("year"))
    slug = slugify(page_url)
    for region_slug in REGIONS:
        marker = f"inclusion-financiere-{region_slug}-"
        if marker in slug:
            tail = slug.split(marker, 1)[1]
            parts = tail.split("-")
            if len(parts) >= 2:
                return REGIONS[region_slug][1], parts[0], int(parts[1])
    raise ValueError(f"unrecognized publication title: {title}")


def extract_pdf_url(html: str, base_url: str) -> tuple[str, Optional[str]]:
    soup = BeautifulSoup(html, "lxml")
    candidates: list[tuple[str, Optional[str], str]] = []
    for anchor in soup.find_all("a", href=True):
        url = urljoin(base_url, anchor["href"].strip())
        if Path(urlparse(url).path).suffix.lower() != ".pdf":
            continue
        text = " ".join(anchor.stripped_strings)
        size = _extract_size(text)
        candidates.append((url, size, text))
    if not candidates:
        raise ValueError("PDF absent")
    preferred = [item for item in candidates if "inclusion" in slugify(f"{item[0]} {item[2]}")]
    url, size, _ = (preferred or candidates)[0]
    return url, size


def _extract_size(text: str) -> Optional[str]:
    match = re.search(r"(\d+(?:[,.]\d+)?)\s*(ko|mo|kb|mb)", text, re.I)
    return match.group(0) if match else None


def extract_date(soup: BeautifulSoup, names: tuple[str, ...]) -> Optional[str]:
    for name in names:
        node = soup.find(attrs={"itemprop": name}) or soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
        value = node.get("content") if node and node.has_attr("content") else node.get_text(" ", strip=True) if node else ""
        if value:
            match = re.search(r"(?:19|20)\d{2}-\d{2}-\d{2}", value)
            if match:
                return match.group(0)
    visible_text = soup.get_text(" ", strip=True)
    label_pattern = "mise en ligne" if any("published" in name or "publication" in name for name in names) else "mise à jour|mise a jour"
    match = re.search(
        rf"(?:{label_pattern})\s+le\s+(?P<day>\d{{1,2}})\s+(?P<month>{'|'.join(MONTHS)})\s+(?P<year>(?:19|20)\d{{2}})",
        visible_text,
        re.I,
    )
    if match:
        return f"{int(match.group('year')):04d}-{month_to_number(match.group('month'))}-{int(match.group('day')):02d}"
    return None


def validate_pdf_response(status_code: int, content_type: str, content: bytes, max_bytes: int = MAX_PDF_BYTES) -> None:
    if not (200 <= status_code < 300):
        raise ValueError("invalid HTTP status")
    if "pdf" not in content_type.lower() and content_type:
        raise ValueError("non PDF MIME type")
    if not content.startswith(b"%PDF-"):
        raise ValueError("non PDF signature")
    if len(content) < MIN_PDF_BYTES:
        raise ValueError("PDF too small")
    if len(content) > max_bytes:
        raise ValueError("PDF too large")


def extract_observations_from_text(text: str, document: DownloadedDocument, page_number: int) -> list[dict]:
    rows: list[dict] = []
    for code, (label, unit, pattern) in INDICATOR_PATTERNS.items():
        match = pattern.search(text)
        extraction_method = "native_text"
        confidence_score = 0.86
        if not match:
            partial_pattern = PARTIAL_TEXT_PATTERNS.get(code)
            match = partial_pattern.search(text) if partial_pattern else None
            extraction_method = "partial_text"
            confidence_score = 0.65
        if not match:
            continue
        raw_value = match.group(1)
        number = parse_french_number(raw_value)
        if number is None:
            continue
        key = idempotence_key(document.pdf_sha256, code, document.metadata.region_code, document.metadata.reference_period, page_number)
        rows.append(
            {
                "idempotence_key": key,
                "indicator_code": code,
                "region_code": document.metadata.region_code,
                "reference_period": document.metadata.reference_period,
                "geographic_level": "region",
                "geographic_code": document.metadata.region_code,
                "geographic_name": document.metadata.region_name,
                "value_numeric": number,
                "value_text": None,
                "unit": unit,
                "observation_type": "monthly",
                "comparison_period": None,
                "variation_numeric": None,
                "variation_unit": None,
                "page_number": page_number,
                "source_label": label,
                "source_fragment": match.group(0)[:500],
                "extraction_method": extraction_method,
                "confidence_score": confidence_score,
            }
        )
    return rows


def ensure_indicators(session) -> None:
    existing = {
        row[0]
        for row in session.execute(select(InclusionIndicator.code)).all()
    }
    for code, (label, unit, _) in INDICATOR_PATTERNS.items():
        if code not in existing:
            session.add(
                InclusionIndicator(
                    code=code,
                    label=label,
                    category="inclusion_financiere",
                    description=label,
                    default_unit=unit,
                )
            )
    session.flush()


def build_intermediate_document(document: DownloadedDocument, observations: list[dict], report: QualityReport) -> dict:
    return {
        "schema_version": "1.0",
        "source": {
            "publisher": PUBLISHER,
            "publication_type": PUBLICATION_TYPE,
            "page_url": document.metadata.page_url,
            "pdf_url": document.metadata.pdf_url,
            "pdf_sha256": document.pdf_sha256,
            "publication_date": document.metadata.publication_date,
            "extractor_version": EXTRACTOR_VERSION,
        },
        "geography": {
            "region_code": document.metadata.region_code,
            "region_name": document.metadata.region_name,
        },
        "reference_period": document.metadata.reference_period,
        "quality": asdict(report),
        "observations": [
            {
                "indicator_code": row["indicator_code"],
                "indicator_label": row["source_label"],
                "value": row["value_numeric"],
                "unit": row["unit"],
                "page_number": row["page_number"],
                "extraction_method": row["extraction_method"],
                "confidence_score": row["confidence_score"],
                "source_fragment": row["source_fragment"],
            }
            for row in observations
        ],
    }


def _parse_regions(values: Optional[list[str]], all_regions: bool) -> Optional[list[str]]:
    if all_regions or not values:
        return None
    parsed: list[str] = []
    for item in values:
        parsed.extend(part.strip() for part in item.split(",") if part.strip())
    return parsed


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect Banque de France regional inclusion-financiere barometers.")
    sub = parser.add_subparsers(dest="command", required=False)
    for name in ("discover", "download", "extract", "load", "run"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--from", dest="from_period", default="2024-01")
        cmd.add_argument("--to", dest="to_period")
        cmd.add_argument("--region", dest="regions", action="append")
        cmd.add_argument("--all-regions", action="store_true")
        cmd.add_argument("--incremental", action="store_true")
        cmd.add_argument("--force", action="store_true")
        cmd.add_argument("--dry-run", action="store_true")
        cmd.add_argument("--max-concurrency", type=int, default=1)
        cmd.add_argument("--output-format", choices=["jsonl"], default="jsonl")
        cmd.add_argument("--listing-url", default=DEFAULT_LISTING_URL)
        cmd.add_argument("--no-load", action="store_true")
        cmd.add_argument("--log-level", default="INFO")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    if not args.command:
        args.command = "run"
    configure_logging(args.log_level)
    pipeline = InclusionFinancialPipeline(listing_url=args.listing_url)
    args.regions = _parse_regions(args.regions, args.all_regions)
    summary = pipeline.run(args)
    print(
        "\n".join(
            [
                f"Pages découvertes : {summary['pages_discovered']}",
                f"PDF nouveaux : {summary['pdf_new']}",
                f"PDF inchangés : {summary['pdf_unchanged']}",
                f"Échecs : {summary['failures']}",
                f"Documents extraits : {summary['documents_extracted']}",
                f"Observations chargées : {summary['observations_loaded']}",
                f"Documents à vérifier : {summary['needs_review']}",
            ]
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
