"""STAT INFO V2 pipeline: scrape PDFs and build a BI-ready department-level CSV."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urldefrag, urljoin, urlparse

import pandas as pd
import pdfplumber
import requests

from src.scraper.downloader import FileDownloader
from src.scraper.parser import ParsedLink, infer_year
from src.utils.config import PipelineConfig
from src.utils.logger import configure_logging, get_logger

DEFAULT_STATINFO_URL = (
    "https://www.banque-france.fr/fr/publications-et-statistiques/statistiques"
    "?theme%5B7168%5D=7168&sub_theme%5B7226%5D=7226"
)
DEFAULT_OUTPUT_CSV = Path("data/processed/statinfo_departements_bi.csv")
MONTHLY_PUBLICATION_SLUG_PATTERN = re.compile(r"depots-dans-les-regions-francaises-(\d{4})-(\d{2})", re.IGNORECASE)
SUPPORTED_PDF_EXTENSIONS = {".pdf"}

DEPARTEMENT_PATTERN = re.compile(r"^(?P<code>(?:\d{2,3}|\d[A-Bab]))\s+(?P<name>.+)$")
YEAR_PATTERN = re.compile(r"(19|20)\d{2}")
TEXT_NUMBER_PATTERN = re.compile(r"-?\d+(?:[,.]\d+)")
MONTH_PATTERN = re.compile(
    r"(janvier|fevrier|février|mars|avril|mai|juin|juillet|aout|août|septembre|octobre|novembre|decembre|décembre)",
    re.IGNORECASE,
)
REFERENCE_PERIOD_PATTERN = re.compile(
    rf"au\s+31\s+(?P<month>{MONTH_PATTERN.pattern})\s+(?P<year>(?:19|20)\d{{2}})",
    re.IGNORECASE,
)
DEPOSITS_REGION_INDICATORS = [
    "Comptes ordinaires créditeurs",
    "Autres livrets (1)",
    "Livrets d'épargne populaire",
    "Livrets de développement durable",
    "C.E.L",
    "Comptes espèces PEA, PER divers",
    "Plans d'épargne populaire",
    "Comptes créditeurs à terme",
    "P.E.L",
    "Bons de caisse et d'épargne (2)",
    "TOTAL",
]
REGION_LABELS = {
    "Auvergne Rhône Alpes",
    "Bourgogne Franche Comté",
    "Bretagne",
    "Centre Val de Loire",
    "Corse",
    "Grand Est",
    "Hauts de France",
    "Ile de France",
    "Normandie",
    "Nouvelle Aquitaine",
    "Occitanie",
    "Pays de la Loire",
    "Provence Alpes Côte d'Azur",
}

TABLE_SETTINGS = [
    None,
    {
        "vertical_strategy": "lines",
        "horizontal_strategy": "lines",
        "snap_tolerance": 3,
        "intersection_tolerance": 3,
    },
    {
        "vertical_strategy": "text",
        "horizontal_strategy": "text",
        "min_words_vertical": 2,
        "min_words_horizontal": 1,
        "snap_tolerance": 3,
    },
]


def run_statinfo_bi_pipeline(
    start_url: str = DEFAULT_STATINFO_URL,
    output_csv: Path = DEFAULT_OUTPUT_CSV,
    max_files: Optional[int] = None,
    skip_crawl: bool = False,
) -> tuple[int, int, int, int]:
    logger = get_logger("statinfo_bi_pipeline")
    config = PipelineConfig.from_env()

    crawled_pages = 0
    downloaded_paths: list[Path] = []

    if skip_crawl:
        downloaded_paths = [
            path for path in sorted(config.output_raw_dir.glob("*.pdf")) if _is_target_raw_pdf(path)
        ]
        if max_files:
            downloaded_paths = downloaded_paths[:max_files]
        logger.info("Skip crawl enabled: using %d existing PDFs from %s", len(downloaded_paths), config.output_raw_dir)
    else:
        listing_html = _fetch_html(start_url, config=config)
        publication_links = _extract_monthly_publication_links(listing_html=listing_html, base_url=start_url)
        if max_files:
            publication_links = publication_links[:max_files]
        crawled_pages = 1 + len(publication_links)

        logger.info("Listing page parsed | Monthly publication pages selected: %d", len(publication_links))

        downloader = FileDownloader(config=config)
        for publication_url in publication_links:
            publication_html = _fetch_html(publication_url, config=config)
            pdf_url = _extract_publication_pdf_url(publication_html=publication_html, base_url=publication_url)
            if not pdf_url:
                logger.warning("No PDF found on publication page: %s", publication_url)
                continue
            link = ParsedLink(
                url=pdf_url,
                text=publication_url.rsplit("/", 1)[-1],
                is_file=True,
                extension=Path(urlparse(pdf_url).path).suffix.lower(),
                relevance_score=1,
                year=infer_year(publication_url, pdf_url),
                region=None,
                dataset_type="depots_regions",
            )
            path = downloader.download_file(link, skip_existing=True)
            if path:
                downloaded_paths.append(path)

    selected_paths = downloaded_paths
    logger.info("Target monthly PDFs selected: %d", len(selected_paths))

    rows: list[dict] = []
    files_with_department_rows = 0
    for path in selected_paths:
        extracted = _extract_department_rows(path)
        if extracted:
            files_with_department_rows += 1
            rows.extend(extracted)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    out_df = pd.DataFrame(rows)
    if out_df.empty:
        logger.warning("No department-level rows extracted from STAT INFO PDFs")
        out_df = pd.DataFrame(
            columns=[
                "reference_year",
                "reference_month",
                "region",
                "departement_code",
                "departement_name",
                "indicator_name",
                "value",
                "source_file",
                "page_number",
            ]
        )
    else:
        out_df = out_df.sort_values(
            ["reference_year", "reference_month", "region", "departement_code", "indicator_name"],
            na_position="last",
        ).reset_index(drop=True)
    out_df.to_csv(output_csv, index=False)
    logger.info("BI CSV exported to %s (%d rows)", output_csv, len(out_df))

    return crawled_pages, len(selected_paths), files_with_department_rows, len(out_df)


def _fetch_html(url: str, config: PipelineConfig) -> str:
    response = requests.get(
        url,
        headers={"User-Agent": config.user_agent},
        timeout=config.timeout_seconds,
    )
    response.raise_for_status()
    return response.text


def _extract_monthly_publication_links(listing_html: str, base_url: str) -> list[str]:
    hrefs = re.findall(r'href=["\']([^"\']+)["\']', listing_html, flags=re.IGNORECASE)
    urls: list[str] = []
    seen: set[str] = set()
    for href in hrefs:
        absolute_url = _normalize_absolute_url(base_url, href)
        if not MONTHLY_PUBLICATION_SLUG_PATTERN.search(absolute_url):
            continue
        if absolute_url in seen:
            continue
        seen.add(absolute_url)
        urls.append(absolute_url)

    fallback_html = _unescape_html_for_pattern_search(listing_html)
    for match in MONTHLY_PUBLICATION_SLUG_PATTERN.finditer(fallback_html):
        year, month = match.groups()
        absolute_url = f"https://www.banque-france.fr/fr/statistiques/monnaie/depots-dans-les-regions-francaises-{year}-{month}"
        if absolute_url in seen:
            continue
        seen.add(absolute_url)
        urls.append(absolute_url)

    return sorted(urls, reverse=True)


def _extract_publication_pdf_url(publication_html: str, base_url: str) -> Optional[str]:
    fallback_html = _unescape_html_for_pattern_search(publication_html)
    expected_pdf_name = _expected_pdf_name_from_publication_url(base_url)
    if expected_pdf_name:
        exact_pdf_pattern = re.compile(
            rf'(https://www\.banque-france\.fr[^\s"\']*{re.escape(expected_pdf_name)}|/[^"\'>\s]*{re.escape(expected_pdf_name)})',
            re.IGNORECASE,
        )
        match = exact_pdf_pattern.search(fallback_html)
        if match:
            return _normalize_absolute_url(base_url, match.group(1))

    hrefs = re.findall(r'href=["\']([^"\']+)["\']', publication_html, flags=re.IGNORECASE)
    pdf_urls: list[str] = []
    for href in hrefs:
        absolute_url = _normalize_absolute_url(base_url, href)
        if Path(urlparse(absolute_url).path).suffix.lower() not in SUPPORTED_PDF_EXTENSIONS:
            continue
        pdf_urls.append(absolute_url)

    prioritized = [
        url for url in pdf_urls if all(token in _normalize_text(url) for token in ["depots", "regions"])
    ]
    if prioritized:
        return prioritized[0]
    return pdf_urls[0] if pdf_urls else None


def _normalize_absolute_url(base_url: str, href: str) -> str:
    absolute = urljoin(base_url, href.strip())
    normalized, _ = urldefrag(absolute)
    return normalized


def _expected_pdf_name_from_publication_url(publication_url: str) -> Optional[str]:
    match = MONTHLY_PUBLICATION_SLUG_PATTERN.search(publication_url)
    if not match:
        return None
    year, month = match.groups()
    return f"FR_Stat_Info_Depots_Regions_{year}_{month}.pdf"


def _unescape_html_for_pattern_search(html: str) -> str:
    return html.replace("\\/", "/")


def _is_target_raw_pdf(path: Path) -> bool:
    normalized = _normalize_text(path.name)
    required_tokens = ["depots", "regions"]
    return path.suffix.lower() == ".pdf" and all(token in normalized for token in required_tokens)


def _extract_department_rows(path: Path) -> list[dict]:
    extracted_rows: list[dict] = []
    try:
        with pdfplumber.open(str(path)) as pdf:
            first_page_text = pdf.pages[0].extract_text() or ""
            reference_year, reference_month = _extract_reference_period(first_page_text, fallback=path.name)

            for page_index, page in enumerate(pdf.pages, start=1):
                text_rows = _extract_rows_from_text_page(
                    text=page.extract_text(x_tolerance=1, y_tolerance=3) or "",
                    reference_year=reference_year,
                    reference_month=reference_month,
                    source_file=path.name,
                    page_number=page_index,
                )
                if text_rows:
                    extracted_rows.extend(text_rows)
                    continue

                table = _extract_best_table(page)
                if not table:
                    continue
                extracted_rows.extend(
                    _extract_rows_from_table(
                        table=table,
                        reference_year=reference_year,
                        reference_month=reference_month,
                        source_file=path.name,
                        page_number=page_index,
                    )
                )
    except Exception:
        return []
    return extracted_rows


def _extract_rows_from_text_page(
    text: str,
    reference_year: Optional[int],
    reference_month: Optional[str],
    source_file: str,
    page_number: int,
) -> list[dict]:
    current_region: Optional[str] = None
    pending_geo_prefix: Optional[str] = None
    output: list[dict] = []

    for raw_line in text.splitlines():
        line = _normalize_cell(raw_line)
        if not line:
            continue

        combined_line = f"{pending_geo_prefix} {line}" if pending_geo_prefix else line
        parsed = _parse_text_data_line(combined_line)
        if parsed is None and pending_geo_prefix:
            parsed = _parse_text_data_line(line)

        if parsed:
            label, values = parsed
            pending_geo_prefix = None
            region_label = _as_known_region_label(label)
            if region_label:
                current_region = region_label
                continue

            match = DEPARTEMENT_PATTERN.match(label)
            if not match:
                continue

            dep_code = match.group("code").upper()
            dep_name = match.group("name").strip()
            for indicator_name, value in zip(DEPOSITS_REGION_INDICATORS, values):
                output.append(
                    {
                        "reference_year": reference_year,
                        "reference_month": reference_month,
                        "region": current_region,
                        "departement_code": dep_code,
                        "departement_name": dep_name,
                        "indicator_name": indicator_name,
                        "value": value,
                        "source_file": source_file,
                        "page_number": page_number,
                    }
                )
            continue

        pending_geo_prefix = line if _is_possible_split_geo_prefix(line) else None

    return output


def _parse_text_data_line(line: str) -> Optional[tuple[str, list[float]]]:
    matches = list(TEXT_NUMBER_PATTERN.finditer(line))
    if len(matches) != len(DEPOSITS_REGION_INDICATORS):
        return None

    label = line[: matches[0].start()].strip()
    if not label:
        return None

    values = [_parse_number(match.group(0)) for match in matches]
    if any(value is None for value in values):
        return None
    return label, [float(value) for value in values if value is not None]


def _is_possible_split_geo_prefix(line: str) -> bool:
    if DEPARTEMENT_PATTERN.match(line):
        return True

    normalized = _normalize_text(line)
    if not normalized:
        return False
    return any(_normalize_text(region).startswith(normalized) for region in REGION_LABELS)


def _as_known_region_label(value: str) -> Optional[str]:
    normalized_value = _normalize_text(value)
    for region in REGION_LABELS:
        if _normalize_text(region) == normalized_value:
            return region
    return None


def _extract_best_table(page) -> Optional[list[list[Optional[str]]]]:
    best_table = None
    best_score = 0
    for settings in TABLE_SETTINGS:
        try:
            tables = page.extract_tables(table_settings=settings) or []
        except Exception:
            continue
        for table in tables:
            score = _table_score(table)
            if score > best_score:
                best_score = score
                best_table = table
    return best_table


def _table_score(table: list[list[Optional[str]]]) -> int:
    if not table:
        return 0
    score = 0
    for row in table:
        if not row:
            continue
        first = _normalize_cell(row[0])
        if not first:
            continue
        if DEPARTEMENT_PATTERN.match(first):
            score += 5
        elif any(ch.isalpha() for ch in first):
            score += 1
        numeric_cells = sum(1 for cell in row[1:] if _parse_number(cell) is not None)
        score += numeric_cells
    return score


def _extract_rows_from_table(
    table: list[list[Optional[str]]],
    reference_year: Optional[int],
    reference_month: Optional[str],
    source_file: str,
    page_number: int,
) -> list[dict]:
    rows = [[_normalize_cell(cell) for cell in row] for row in table if row]
    if len(rows) < 3:
        return []

    first_data_idx = _find_first_data_row(rows)
    if first_data_idx is None:
        return []

    headers = _build_column_headers(rows[:first_data_idx], column_count=max(len(r) for r in rows))
    current_region: Optional[str] = None
    output: list[dict] = []

    for row in rows[first_data_idx:]:
        if not row:
            continue
        geo = row[0] if len(row) > 0 else ""
        if not geo:
            continue

        region_label = _as_region_label(geo)
        if region_label:
            current_region = region_label
            continue

        match = DEPARTEMENT_PATTERN.match(geo)
        if not match:
            continue

        dep_code = match.group("code").upper()
        dep_name = match.group("name").strip()

        for col_idx in range(1, min(len(row), len(headers))):
            indicator_name = headers[col_idx]
            value = _parse_number(row[col_idx])
            if value is None:
                continue
            if not indicator_name or indicator_name.startswith("col_"):
                continue
            output.append(
                {
                    "reference_year": reference_year,
                    "reference_month": reference_month,
                    "region": current_region,
                    "departement_code": dep_code,
                    "departement_name": dep_name,
                    "indicator_name": indicator_name,
                    "value": value,
                    "source_file": source_file,
                    "page_number": page_number,
                }
            )

    return output


def _find_first_data_row(rows: list[list[str]]) -> Optional[int]:
    for idx, row in enumerate(rows):
        if not row:
            continue
        first = row[0] if len(row) > 0 else ""
        if not first:
            continue
        numeric_count = sum(1 for cell in row[1:] if _parse_number(cell) is not None)
        if numeric_count >= 3 and (DEPARTEMENT_PATTERN.match(first) or _as_region_label(first) is not None):
            return idx
    return None


def _build_column_headers(header_rows: Iterable[list[str]], column_count: int) -> list[str]:
    headers = ["col_0"]
    joined_rows = list(header_rows)
    for col_idx in range(1, column_count):
        parts: list[str] = []
        for row in joined_rows:
            value = row[col_idx] if col_idx < len(row) else ""
            if value and value not in parts:
                parts.append(value)
        header = " ".join(parts).strip()
        header = re.sub(r"\s+", " ", header)
        headers.append(header or f"col_{col_idx}")
    return headers


def _as_region_label(value: str) -> Optional[str]:
    normalized = value.strip()
    if not normalized:
        return None
    if DEPARTEMENT_PATTERN.match(normalized):
        return None
    lowered = _normalize_text(normalized)
    if "france" in lowered and "metropolitaine" in lowered:
        return "France metropolitaine"
    if any(ch.isalpha() for ch in normalized):
        return normalized.replace("*", "").strip()
    return None


def _normalize_cell(value: Optional[str]) -> str:
    if value is None:
        return ""
    text = str(value).replace("\n", " ").replace("\u00a0", " ").strip()
    return re.sub(r"\s+", " ", text)


def _parse_number(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    text = _normalize_cell(value)
    if not text:
        return None
    text = text.replace(" ", "").replace(",", ".")
    text = re.sub(r"[^0-9\.\-]", "", text)
    if not text or text in {"-", ".", "-."}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _extract_year(text: str, fallback: str) -> Optional[int]:
    combined = f"{text} {fallback}"
    match = YEAR_PATTERN.search(combined)
    return int(match.group(0)) if match else None


def _extract_month(text: str) -> Optional[str]:
    match = MONTH_PATTERN.search(text)
    return match.group(1).lower() if match else None


def _extract_reference_period(text: str, fallback: str) -> tuple[Optional[int], Optional[str]]:
    match = REFERENCE_PERIOD_PATTERN.search(text)
    if match:
        return int(match.group("year")), match.group("month").lower()
    return _extract_year(text, fallback=fallback), _extract_month(text)


def _normalize_text(text: str) -> str:
    lowered = text.lower()
    lowered = (
        lowered.replace("é", "e")
        .replace("è", "e")
        .replace("ê", "e")
        .replace("ë", "e")
        .replace("à", "a")
        .replace("â", "a")
        .replace("î", "i")
        .replace("ï", "i")
        .replace("ô", "o")
        .replace("ö", "o")
        .replace("ù", "u")
        .replace("û", "u")
        .replace("ü", "u")
        .replace("ç", "c")
        .replace("’", "'")
    )
    lowered = re.sub(r"[^a-z0-9'\s]", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "V2 BI pipeline for STAT INFO PDFs: scrape, store raw PDFs, and export "
            "department-level normalized CSV."
        )
    )
    parser.add_argument("--start-url", default=DEFAULT_STATINFO_URL, help="Target listing URL.")
    parser.add_argument("--output-csv", default=str(DEFAULT_OUTPUT_CSV), help="Output CSV path.")
    parser.add_argument("--max-files", type=int, default=None, help="Optional cap on processed PDFs.")
    parser.add_argument(
        "--skip-crawl",
        action="store_true",
        help="Use existing PDFs already present in data/raw instead of crawling/downloading.",
    )
    parser.add_argument("--log-level", default="INFO", help="Log level.")
    return parser


def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()
    configure_logging(args.log_level)

    pages, selected_pdfs, extracted_files, rows = run_statinfo_bi_pipeline(
        start_url=args.start_url,
        output_csv=Path(args.output_csv),
        max_files=args.max_files,
        skip_crawl=args.skip_crawl,
    )

    print(
        "STAT INFO BI pipeline completed | "
        f"pages_crawled={pages} "
        f"target_pdfs={selected_pdfs} "
        f"files_with_departements={extracted_files} "
        f"rows_exported={rows}"
    )


if __name__ == "__main__":
    main()
