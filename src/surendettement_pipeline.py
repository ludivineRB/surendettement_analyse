"""Validated pipeline for department-level over-indebtedness filings."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.scraper.downloader import FileDownloader
from src.scraper.parser import ParsedLink
from src.scraper.spider import BanqueFranceSpider
from src.statinfo_bi_quality import EXPECTED_DEPARTMENT_CODES
from src.utils.config import PipelineConfig
from src.utils.departments import normalize_department_code
from src.utils.logger import configure_logging, get_logger

RAW_DIR = Path("data/raw/surendettement")
GOLD_DIR = Path("data/processed/surendettement/gold")
DEFAULT_GOLD_CSV = GOLD_DIR / "surendettement_departements.csv"
SUPPORTED_STRUCTURED_EXTENSIONS = {".csv", ".xlsx"}
TARGET_COLUMNS = [
    "reference_year",
    "reference_month",
    "departement_code",
    "departement_name",
    "indicator_code",
    "indicator_name",
    "value",
    "source_file",
]

LOGGER = get_logger(__name__)


@dataclass(slots=True)
class SurendettementPipelineSummary:
    pages_crawled: int = 0
    files_discovered: int = 0
    files_selected_for_download: int = 0
    files_downloaded: int = 0
    files_processed: int = 0
    files_rejected: int = 0
    output_rows: int = 0
    departments: int = 0


def discover_structured_sources(source_dir: Path = RAW_DIR, output_csv: Path | None = None) -> pd.DataFrame:
    """Crawl BDF and return structured source candidates for manual inspection."""
    source_dir.mkdir(parents=True, exist_ok=True)
    summary = SurendettementPipelineSummary()
    links = _crawl_structured_links(summary)
    rows = [
        {
            "text": link.text,
            "url": link.url,
            "extension": link.extension,
            "year": link.year,
            "dataset_type": link.dataset_type,
            "is_selected_for_download": _is_relevant_structured_link(link),
        }
        for link in links
    ]
    report = pd.DataFrame(rows)
    if output_csv:
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        report.to_csv(output_csv, index=False)
    return report


def profile_local_sources(source_dir: Path = RAW_DIR, output_csv: Path | None = None) -> pd.DataFrame:
    """Describe local CSV/XLSX files to identify useful source structures."""
    rows: list[dict[str, object]] = []
    for path in _discover_local_sources(source_dir):
        rows.extend(_profile_source(path))
    report = pd.DataFrame(rows)
    if output_csv:
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        report.to_csv(output_csv, index=False)
    return report


def run_surendettement_pipeline(
    skip_crawl: bool = False,
    source_dir: Path = RAW_DIR,
    output_csv: Path = DEFAULT_GOLD_CSV,
    max_files: int | None = None,
    download_all_discovered: bool = False,
) -> SurendettementPipelineSummary:
    """Build the gold department filings dataset from structured BDF sources."""
    summary = SurendettementPipelineSummary()
    source_dir.mkdir(parents=True, exist_ok=True)

    paths = (
        _discover_local_sources(source_dir)
        if skip_crawl
        else _crawl_and_download(source_dir, summary, download_all_discovered=download_all_discovered)
    )
    if max_files:
        paths = paths[:max_files]

    frames: list[pd.DataFrame] = []
    for path in paths:
        try:
            frame = parse_structured_source(path)
        except ValueError as exc:
            summary.files_rejected += 1
            LOGGER.warning("Rejected %s: %s", path, exc)
            continue
        frames.append(frame)
        summary.files_processed += 1

    try:
        gold = build_gold_dataset(frames)
    except ValueError as exc:
        LOGGER.warning("No gold dataset exported: %s", exc)
        gold = pd.DataFrame(columns=TARGET_COLUMNS)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    gold.to_csv(output_csv, index=False)
    summary.output_rows = len(gold)
    summary.departments = gold["departement_code"].nunique() if not gold.empty else 0
    return summary


def parse_structured_source(path: Path) -> pd.DataFrame:
    """Parse one structured source and return canonical department-level rows."""
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_STRUCTURED_EXTENSIONS:
        raise ValueError("Only CSV/XLSX structured sources are accepted for gold surendettement data.")

    frames = _read_frames(path)
    candidates = []
    for frame in frames:
        normalized = _normalize_source_frame(frame, source_file=path.name)
        if not normalized.empty:
            candidates.append(normalized)

    if not candidates:
        raise ValueError("No valid department-level filings table found.")

    result = pd.concat(candidates, ignore_index=True)
    _validate_gold_quality(result, source_name=path.name, require_national_coverage=False)
    return result[TARGET_COLUMNS]


def build_gold_dataset(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Concatenate and de-duplicate validated source frames."""
    if not frames:
        return pd.DataFrame(columns=TARGET_COLUMNS)

    gold = pd.concat(frames, ignore_index=True)
    gold = gold.drop_duplicates(
        ["reference_year", "reference_month", "departement_code", "indicator_code", "source_file"]
    )
    gold = gold.sort_values(["reference_year", "reference_month", "departement_code", "indicator_code"])
    _validate_gold_quality(gold, source_name="combined sources", require_national_coverage=True)
    return gold[TARGET_COLUMNS]


def _crawl_and_download(
    source_dir: Path,
    summary: SurendettementPipelineSummary,
    download_all_discovered: bool = False,
) -> list[Path]:
    links = _crawl_structured_links(summary)
    if download_all_discovered or _has_targeted_start_url():
        candidates = links
    else:
        candidates = [link for link in links if _is_relevant_structured_link(link)]
    summary.files_selected_for_download = len(candidates)
    config = _surendettement_config(output_raw_dir=source_dir)
    downloader = FileDownloader(config=config)
    paths = [path for path in (downloader.download_file(link, skip_existing=True) for link in candidates) if path]
    summary.files_downloaded = len(paths)
    return paths


def _crawl_structured_links(summary: SurendettementPipelineSummary) -> list[ParsedLink]:
    config = _surendettement_config()
    spider = BanqueFranceSpider(config=config)
    result = spider.crawl()
    summary.pages_crawled = len(result.pages)
    summary.files_discovered = len(result.files)
    return result.files


def _surendettement_config(output_raw_dir: Path | None = None) -> PipelineConfig:
    config = PipelineConfig.from_env()
    config.file_extensions = sorted(SUPPORTED_STRUCTURED_EXTENSIONS)
    config.keywords = ["surendettement", "typologie", "endettement"]
    if output_raw_dir is not None:
        config.output_raw_dir = output_raw_dir
    if config.start_urls:
        config.base_url = config.start_urls[0]
    return config


def _has_targeted_start_url() -> bool:
    config = PipelineConfig.from_env()
    haystack = " ".join(config.start_urls).lower()
    return "surendettement" in haystack or "typologie" in haystack


def _discover_local_sources(source_dir: Path) -> list[Path]:
    return sorted(path for path in source_dir.glob("*") if path.suffix.lower() in SUPPORTED_STRUCTURED_EXTENSIONS)


def _is_relevant_structured_link(link: ParsedLink) -> bool:
    haystack = f"{link.text} {link.url}".lower()
    has_topic = "surendettement" in haystack or "typologie" in haystack
    return link.extension.lower() in SUPPORTED_STRUCTURED_EXTENSIONS and has_topic


def _read_frames(path: Path) -> list[pd.DataFrame]:
    if path.suffix.lower() == ".csv":
        return [_read_csv(path)]
    workbook = pd.read_excel(path, sheet_name=None, engine="openpyxl")
    return [frame for frame in workbook.values() if frame is not None and not frame.empty]


def _read_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path, sep=None, engine="python")
    except Exception:
        return pd.read_csv(path)


def _profile_source(path: Path) -> list[dict[str, object]]:
    try:
        if path.suffix.lower() == ".csv":
            frame = _read_csv(path)
            return [_profile_frame(path, "csv", frame)]
        workbook = pd.read_excel(path, sheet_name=None, engine="openpyxl", nrows=10)
        return [_profile_frame(path, sheet_name, frame) for sheet_name, frame in workbook.items()]
    except Exception as exc:
        return [
            {
                "source_file": path.name,
                "sheet_name": None,
                "rows_sampled": 0,
                "columns": None,
                "error": str(exc),
            }
        ]


def _profile_frame(path: Path, sheet_name: str, frame: pd.DataFrame) -> dict[str, object]:
    columns = [_normalize_column_name(column) for column in frame.columns]
    keywords = " ".join([path.name, sheet_name, *columns]).lower()
    return {
        "source_file": path.name,
        "sheet_name": sheet_name,
        "rows_sampled": len(frame),
        "columns": " | ".join(columns),
        "mentions_surendettement": "surendettement" in keywords,
        "mentions_departement": "departement" in keywords or "dep" in columns,
        "mentions_dossiers": "dossier" in keywords,
        "error": None,
    }


def _normalize_source_frame(frame: pd.DataFrame, source_file: str) -> pd.DataFrame:
    cleaned = frame.copy()
    cleaned.columns = [_normalize_column_name(column) for column in cleaned.columns]
    cleaned = cleaned.dropna(axis=0, how="all").dropna(axis=1, how="all")
    if cleaned.empty:
        return pd.DataFrame(columns=TARGET_COLUMNS)

    year_col = _find_column(cleaned, ["reference_year", "annee", "year", "exercice"])
    month_col = _find_column(cleaned, ["reference_month", "mois", "month", "periode", "period"])
    dept_col = _find_column(cleaned, ["departement_code", "code_departement", "dep", "departement"])
    dept_name_col = _find_column(cleaned, ["departement_name", "libelle_departement", "nom_departement"])
    value_col = _find_column(
        cleaned,
        [
            "dossiers_deposes",
            "nombre_dossiers_deposes",
            "nb_dossiers_deposes",
            "dossiers",
            "nombre",
            "value",
        ],
    )

    if not year_col or not dept_col or not value_col:
        return pd.DataFrame(columns=TARGET_COLUMNS)

    output = pd.DataFrame()
    output["reference_year"] = pd.to_numeric(cleaned[year_col], errors="coerce").astype("Int64")
    output["reference_month"] = _coerce_month(cleaned[month_col]) if month_col else pd.Series([pd.NA] * len(cleaned))
    output["departement_code"] = cleaned[dept_col].map(normalize_department_code)
    output["departement_name"] = cleaned[dept_name_col].astype(str).str.strip() if dept_name_col else pd.NA
    output["indicator_code"] = "dossiers_deposes"
    output["indicator_name"] = "Nombre de dossiers déposés"
    output["value"] = pd.to_numeric(cleaned[value_col], errors="coerce")
    output["source_file"] = source_file
    output = output.dropna(subset=["reference_year", "departement_code", "value"]).copy()
    output["reference_year"] = output["reference_year"].astype(int)
    output["value"] = output["value"].astype(float)
    output = output[output["departement_code"].isin(EXPECTED_DEPARTMENT_CODES)]
    return output[TARGET_COLUMNS]


def _validate_gold_quality(df: pd.DataFrame, source_name: str, require_national_coverage: bool) -> None:
    if df.empty:
        return
    invalid_codes = sorted(set(df["departement_code"].dropna()) - set(EXPECTED_DEPARTMENT_CODES))
    if invalid_codes:
        raise ValueError(f"{source_name}: invalid metropolitan department codes: {invalid_codes[:10]}")
    if (df["value"] < 0).any():
        raise ValueError(f"{source_name}: negative filings values found.")
    min_departments = 50 if require_national_coverage else 1
    if df["departement_code"].nunique() < min_departments:
        raise ValueError(
            f"{source_name}: only {df['departement_code'].nunique()} departments found; "
            f"expected at least {min_departments}."
        )


def _normalize_column_name(value: object) -> str:
    text = str(value).strip().lower()
    replacements = str.maketrans("àâäéèêëîïôöùûüç'’", "aaaeeeeiioouuuc__")
    text = text.translate(replacements)
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def _find_column(df: pd.DataFrame, aliases: list[str]) -> str | None:
    aliases = [_normalize_column_name(alias) for alias in aliases]
    for alias in aliases:
        if alias in df.columns:
            return alias
    for column in df.columns:
        if any(alias in column for alias in aliases):
            return column
    return None


def _coerce_month(series: pd.Series) -> pd.Series:
    month_names = {
        "janvier": 1,
        "fevrier": 2,
        "février": 2,
        "mars": 3,
        "avril": 4,
        "mai": 5,
        "juin": 6,
        "juillet": 7,
        "aout": 8,
        "août": 8,
        "septembre": 9,
        "octobre": 10,
        "novembre": 11,
        "decembre": 12,
        "décembre": 12,
    }
    normalized = series.astype(str).str.strip().str.lower()
    numeric = pd.to_numeric(normalized, errors="coerce")
    named = normalized.map(month_names)
    if numeric.notna().any() and named.notna().any():
        return numeric.combine_first(named).astype("Int64")
    if numeric.notna().any():
        return numeric.astype("Int64")
    return named.astype("Int64")


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build validated department-level surendettement data.")
    parser.add_argument("--skip-crawl", action="store_true", help="Use local CSV/XLSX files only.")
    parser.add_argument(
        "--download-all-discovered",
        action="store_true",
        help="Download every discovered CSV/XLSX, then let validation reject non-surendettement files.",
    )
    parser.add_argument("--list-discovered", action="store_true", help="List discovered structured sources without downloading.")
    parser.add_argument("--profile-local", action="store_true", help="Profile local downloaded CSV/XLSX files without parsing.")
    parser.add_argument(
        "--discovery-csv",
        default="data/processed/surendettement/discovered_sources.csv",
        help="Output path for --list-discovered.",
    )
    parser.add_argument(
        "--profile-csv",
        default="data/processed/surendettement/local_source_profile.csv",
        help="Output path for --profile-local.",
    )
    parser.add_argument("--source-dir", default=str(RAW_DIR))
    parser.add_argument("--output-csv", default=str(DEFAULT_GOLD_CSV))
    parser.add_argument("--max-files", type=int, default=None)
    parser.add_argument("--log-level", default=None)
    return parser


def main() -> None:
    args = _build_arg_parser().parse_args()
    configure_logging(args.log_level or PipelineConfig.from_env().log_level)
    if args.list_discovered:
        report = discover_structured_sources(source_dir=Path(args.source_dir), output_csv=Path(args.discovery_csv))
        selected = int(report["is_selected_for_download"].sum()) if not report.empty else 0
        print(
            "Surendettement discovery completed | "
            f"files_discovered={len(report)} "
            f"files_selected_for_download={selected} "
            f"discovery_csv={args.discovery_csv}"
        )
        return
    if args.profile_local:
        report = profile_local_sources(source_dir=Path(args.source_dir), output_csv=Path(args.profile_csv))
        relevant = report[
            report[["mentions_surendettement", "mentions_departement", "mentions_dossiers"]]
            .fillna(False)
            .any(axis=1)
        ]
        print(
            "Surendettement local profile completed | "
            f"files_or_sheets={len(report)} "
            f"potentially_relevant={len(relevant)} "
            f"profile_csv={args.profile_csv}"
        )
        return

    summary = run_surendettement_pipeline(
        skip_crawl=args.skip_crawl,
        source_dir=Path(args.source_dir),
        output_csv=Path(args.output_csv),
        max_files=args.max_files,
        download_all_discovered=args.download_all_discovered,
    )
    print(
        "Surendettement pipeline completed | "
        f"pages_crawled={summary.pages_crawled} "
        f"files_discovered={summary.files_discovered} "
        f"files_selected_for_download={summary.files_selected_for_download} "
        f"files_downloaded={summary.files_downloaded} "
        f"files_processed={summary.files_processed} "
        f"files_rejected={summary.files_rejected} "
        f"output_rows={summary.output_rows} "
        f"departments={summary.departments}"
    )


if __name__ == "__main__":
    main()
