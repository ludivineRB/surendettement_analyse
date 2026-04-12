"""Dedicated chain for Banque de France STAT INFO PDF scraping and extraction."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.processing.ingest import FileMetadata, normalize_files
from src.processing.transform import build_unified_frame
from src.processing.validation import validate_non_empty, validate_schema
from src.scraper.downloader import FileDownloader
from src.scraper.spider import BanqueFranceSpider
from src.utils.config import PipelineConfig
from src.utils.logger import configure_logging, get_logger

DEFAULT_STATINFO_URL = (
    "https://www.banque-france.fr/fr/publications-et-statistiques/statistiques"
    "?theme%5B7168%5D=7168&sub_theme%5B7226%5D=7226"
)
DEFAULT_KEYWORDS = [
    "stat info",
    "depots",
    "dépôts",
    "epargne",
    "épargne",
    "comptes",
    "regions",
    "régions",
]


def run_statinfo_pipeline(
    start_url: str,
    max_files: int | None = None,
    output_csv: Path = Path("data/processed/statinfo_unified.csv"),
) -> tuple[int, int, int]:
    config = PipelineConfig.from_env()
    config.start_urls = [start_url]
    config.max_depth = min(config.max_depth, 2)
    config.max_pages = min(config.max_pages, 200)

    logger = get_logger("statinfo_pipeline")
    spider = BanqueFranceSpider(config=config)
    crawl_result = spider.crawl()

    pdf_links = [
        link
        for link in crawl_result.files
        if link.extension.lower() == ".pdf"
        and any(kw in f"{link.text} {link.url}".lower() for kw in DEFAULT_KEYWORDS)
    ]
    if max_files:
        pdf_links = pdf_links[:max_files]

    logger.info(
        "Pages crawled: %d | PDF links selected: %d",
        len(crawl_result.pages),
        len(pdf_links),
    )

    downloader = FileDownloader(config=config)
    downloaded_paths = []
    metadata_map: dict[Path, FileMetadata] = {}
    for link in pdf_links:
        local_path = downloader.download_file(link, skip_existing=True)
        if not local_path:
            continue
        downloaded_paths.append(local_path)
        metadata_map[local_path] = FileMetadata(
            year=link.year,
            region=link.region,
            dataset_type="statinfo",
        )

    normalized_frames = normalize_files(downloaded_paths, metadata_map=metadata_map)
    unified = build_unified_frame(normalized_frames)

    schema_result = validate_schema(unified)
    if not schema_result.is_valid:
        raise ValueError(f"Schema validation failed: {schema_result.errors}")

    non_empty_result = validate_non_empty(unified)
    if not non_empty_result.is_valid:
        logger.warning("No rows extracted from selected STAT INFO PDFs")
        return len(crawl_result.pages), len(downloaded_paths), 0

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    unified.to_csv(output_csv, index=False)
    logger.info("STAT INFO unified dataset exported to %s", output_csv)
    return len(crawl_result.pages), len(downloaded_paths), len(unified)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scrape Banque de France STAT INFO PDFs, store raw files, and extract tables to CSV."
    )
    parser.add_argument(
        "--start-url",
        default=DEFAULT_STATINFO_URL,
        help="STAT INFO listing page URL.",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help="Optional cap on number of PDFs to process.",
    )
    parser.add_argument(
        "--output-csv",
        default="data/processed/statinfo_unified.csv",
        help="Output CSV path.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Log level (INFO, DEBUG...).",
    )
    return parser


def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()
    configure_logging(args.log_level)

    pages, files, rows = run_statinfo_pipeline(
        start_url=args.start_url,
        max_files=args.max_files,
        output_csv=Path(args.output_csv),
    )
    print(
        "STAT INFO pipeline completed | "
        f"pages_crawled={pages} "
        f"pdf_downloaded={files} "
        f"rows_extracted={rows}"
    )


if __name__ == "__main__":
    main()
