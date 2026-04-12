"""STAT INFO V2 pipeline: scrape PDFs and build a BI-ready department-level CSV."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd
import pdfplumber

from src.scraper.downloader import FileDownloader
from src.scraper.spider import BanqueFranceSpider
from src.utils.config import PipelineConfig
from src.utils.logger import configure_logging, get_logger

DEFAULT_STATINFO_URL = (
    "https://www.banque-france.fr/fr/publications-et-statistiques/statistiques"
    "?theme%5B7168%5D=7168&sub_theme%5B7226%5D=7226"
)
DEFAULT_OUTPUT_CSV = Path("data/processed/statinfo_departements_bi.csv")

DEPARTEMENT_PATTERN = re.compile(r"^(?P<code>\d{2,3}[A-Bab]?)\s+(?P<name>.+)$")
YEAR_PATTERN = re.compile(r"(19|20)\d{2}")
MONTH_PATTERN = re.compile(
    r"(janvier|fevrier|février|mars|avril|mai|juin|juillet|aout|août|septembre|octobre|novembre|decembre|décembre)",
    re.IGNORECASE,
)

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
    config.start_urls = [start_url]
    config.max_depth = min(config.max_depth, 2)
    config.max_pages = min(config.max_pages, 250)
    config.file_extensions = [".pdf"]

    crawled_pages = 0
    downloaded_paths: list[Path] = []

    if skip_crawl:
        downloaded_paths = sorted(config.output_raw_dir.glob("*.pdf"))
        if max_files:
            downloaded_paths = downloaded_paths[:max_files]
        logger.info("Skip crawl enabled: using %d existing PDFs from %s", len(downloaded_paths), config.output_raw_dir)
    else:
        spider = BanqueFranceSpider(config=config)
        crawl_result = spider.crawl()
        crawled_pages = len(crawl_result.pages)
        pdf_links = [link for link in crawl_result.files if link.extension.lower() == ".pdf"]
        if max_files:
            pdf_links = pdf_links[:max_files]

        logger.info("Crawled pages: %d | Candidate PDF links: %d", len(crawl_result.pages), len(pdf_links))

        downloader = FileDownloader(config=config)
        for link in pdf_links:
            path = downloader.download_file(link, skip_existing=True)
            if path:
                downloaded_paths.append(path)

    selected_paths = [p for p in downloaded_paths if _is_target_statinfo_pdf(p)]
    logger.info("Downloaded PDFs: %d | Target STAT INFO PDFs: %d", len(downloaded_paths), len(selected_paths))

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


def _is_target_statinfo_pdf(path: Path) -> bool:
    try:
        with pdfplumber.open(str(path)) as pdf:
            if not pdf.pages:
                return False
            text = " ".join((pdf.pages[i].extract_text() or "") for i in range(min(3, len(pdf.pages))))
    except Exception:
        return False

    normalized = _normalize_text(text)
    if "depots et comptes d epargne dans les regions francaises" in normalized:
        return True

    required_tokens = ["stat", "info", "depots", "epargne", "regions", "francaises"]
    return all(token in normalized for token in required_tokens)


def _extract_department_rows(path: Path) -> list[dict]:
    extracted_rows: list[dict] = []
    try:
        with pdfplumber.open(str(path)) as pdf:
            first_page_text = pdf.pages[0].extract_text() or ""
            reference_year = _extract_year(first_page_text, fallback=path.name)
            reference_month = _extract_month(first_page_text)

            for page_index, page in enumerate(pdf.pages, start=1):
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
