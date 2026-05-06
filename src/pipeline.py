"""CLI entrypoint for the full surendettement ingestion pipeline."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from src.processing.ingest import FileMetadata, normalize_files
from src.processing.transform import build_unified_frame
from src.processing.validation import validate_non_empty, validate_schema
from src.scraper.downloader import FileDownloader
from src.scraper.spider import BanqueFranceSpider
from src.storage.database import get_existing_source_files, init_db, save_dataframe
from src.utils.config import PipelineConfig
from src.utils.logger import configure_logging, get_logger


@dataclass(slots=True)
class PipelineRunSummary:
    pages_crawled: int = 0
    files_discovered: int = 0
    files_downloaded: int = 0
    files_already_ingested: int = 0
    files_selected_for_processing: int = 0
    normalized_frames: int = 0
    final_rows: int = 0
    rows_inserted: int = 0


def _is_surendettement_candidate_name(value: str) -> bool:
    normalized = value.lower()
    return "surendettement" in normalized or "typologie" in normalized


def _is_relevant_surendettement_link(text: str, url: str) -> bool:
    haystack = f"{text} {url}".lower()
    return _is_surendettement_candidate_name(haystack)


def _is_relevant_raw_path(path: Path) -> bool:
    return _is_surendettement_candidate_name(path.name)


def run_pipeline(
    skip_crawl: bool = False,
    max_files: int | None = None,
    only_new_data: bool = True,
) -> PipelineRunSummary:
    """Execute crawl -> download -> parse -> normalize -> store."""
    config = PipelineConfig.from_env()
    logger = get_logger("pipeline")
    summary = PipelineRunSummary()

    downloaded_paths: List[Path] = []
    metadata_map: Dict[Path, FileMetadata] = {}

    if skip_crawl:
        downloaded_paths = [path for path in sorted(config.output_raw_dir.glob("*")) if _is_relevant_raw_path(path)]
        logger.info("Skipping crawl: using %d existing raw files from %s", len(downloaded_paths), config.output_raw_dir)
    else:
        spider = BanqueFranceSpider(config=config)
        crawl_result = spider.crawl()
        summary.pages_crawled = len(crawl_result.pages)
        summary.files_discovered = len(crawl_result.files)
        relevant_files = [
            link for link in crawl_result.files if _is_relevant_surendettement_link(link.text, link.url)
        ]
        candidate_files = relevant_files[:max_files] if max_files else relevant_files

        downloader = FileDownloader(config=config)
        for link in candidate_files:
            local_path = downloader.download_file(link, skip_existing=True)
            if not local_path:
                continue
            downloaded_paths.append(local_path)
            metadata_map[local_path] = FileMetadata(
                year=link.year,
                region=link.region,
                dataset_type=link.dataset_type,
            )

        summary.files_downloaded = len(downloaded_paths)
        logger.info(
            "Discovered files: %d | Relevant surendettement files: %d | Downloaded files: %d",
            summary.files_discovered,
            len(relevant_files),
            summary.files_downloaded,
        )

    if max_files and skip_crawl:
        downloaded_paths = downloaded_paths[:max_files]

    # Remove path duplicates while preserving order.
    unique_paths = list(dict.fromkeys(downloaded_paths))

    selected_paths = unique_paths
    if only_new_data:
        existing_sources = get_existing_source_files()
        selected_paths = [path for path in unique_paths if path.name not in existing_sources]
        summary.files_already_ingested = len(unique_paths) - len(selected_paths)
        logger.info(
            "Already ingested files skipped: %d | Remaining files to process: %d",
            summary.files_already_ingested,
            len(selected_paths),
        )

    summary.files_selected_for_processing = len(selected_paths)
    normalized_frames = normalize_files(selected_paths, metadata_map=metadata_map)
    summary.normalized_frames = len(normalized_frames)
    unified = build_unified_frame(normalized_frames)
    summary.final_rows = len(unified)

    schema_result = validate_schema(unified)
    if not schema_result.is_valid:
        raise ValueError(f"Schema validation failed: {schema_result.errors}")

    non_empty_result = validate_non_empty(unified)
    if not non_empty_result.is_valid:
        logger.warning("No rows to persist: %s", non_empty_result.errors[0])
        return summary

    processed_dir = Path("data/processed")
    processed_dir.mkdir(parents=True, exist_ok=True)
    output_path = processed_dir / "surendettement_unified.csv"
    unified.to_csv(output_path, index=False)
    logger.info("Unified dataset exported to %s", output_path)

    init_db()
    summary.rows_inserted = save_dataframe(unified)
    logger.info("Inserted %d rows into database", summary.rows_inserted)
    return summary


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run surendettement ingestion pipeline.")
    parser.add_argument(
        "--skip-crawl",
        action="store_true",
        help="Skip crawling/downloading and use existing files in data/raw.",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help="Optional cap on the number of files to process.",
    )
    parser.add_argument(
        "--log-level",
        default=None,
        help="Optional log level override (e.g. INFO, DEBUG).",
    )
    parser.add_argument(
        "--reprocess-all",
        action="store_true",
        help="Process all discovered/raw files, including files already present in database.",
    )
    return parser


def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()

    if args.log_level:
        configure_logging(args.log_level)
    else:
        configure_logging(PipelineConfig.from_env().log_level)

    summary = run_pipeline(
        skip_crawl=args.skip_crawl,
        max_files=args.max_files,
        only_new_data=not args.reprocess_all,
    )
    print(
        (
            "Pipeline completed | "
            f"pages_crawled={summary.pages_crawled} "
            f"files_discovered={summary.files_discovered} "
            f"files_downloaded={summary.files_downloaded} "
            f"files_already_ingested={summary.files_already_ingested} "
            f"files_selected_for_processing={summary.files_selected_for_processing} "
            f"normalized_frames={summary.normalized_frames} "
            f"final_rows={summary.final_rows} "
            f"rows_inserted={summary.rows_inserted}"
        )
    )


if __name__ == "__main__":
    main()
