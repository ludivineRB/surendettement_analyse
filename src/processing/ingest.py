"""File ingestion and normalization utilities for raw datasets."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

import pandas as pd
import pdfplumber

from src.processing.clean import normalize_columns
from src.processing.transform import append_source_file
from src.utils.logger import get_logger

YEAR_PATTERN = re.compile(r"(19|20)\d{2}")

YEAR_ALIASES = ("year", "annee", "année", "exercice")
DEPARTEMENT_ALIASES = ("departement", "département", "region", "région", "territoire")
INDICATOR_ALIASES = (
    "indicator_name",
    "indicator",
    "indicateur",
    "libelle",
    "libellé",
    "categorie",
    "catégorie",
    "variable",
)
VALUE_ALIASES = ("value", "valeur", "nombre", "nb", "montant", "taux")

TARGET_COLUMNS = ["year", "departement", "indicator_name", "value", "source_file"]
LOGGER = get_logger(__name__)
NON_BREAKING_SPACE = "\u00a0"


@dataclass(slots=True)
class FileMetadata:
    year: Optional[int] = None
    region: Optional[str] = None
    dataset_type: str = "unknown"


def infer_year_from_name(path: Path) -> Optional[int]:
    match = YEAR_PATTERN.search(path.name)
    return int(match.group(0)) if match else None


def load_file_frames(path: Path) -> List[pd.DataFrame]:
    """Load raw file into one or more dataframes."""
    suffix = path.suffix.lower()
    try:
        if suffix == ".xlsx":
            return _read_excel_all_sheets(path)
        if suffix == ".csv":
            return _read_csv(path)
        if suffix == ".pdf":
            return _read_pdf_tables(path)
        return []
    except Exception as exc:
        LOGGER.warning("Failed to parse %s: %s", path, exc)
        return []


def _read_excel_all_sheets(path: Path) -> List[pd.DataFrame]:
    try:
        workbook = pd.read_excel(path, sheet_name=None, engine="openpyxl")
    except ImportError as exc:
        LOGGER.warning("openpyxl is required to read Excel file %s: %s", path, exc)
        return []
    frames: List[pd.DataFrame] = []
    for _, frame in workbook.items():
        if frame is not None and not frame.empty:
            frames.append(frame)
    return frames


def _read_csv(path: Path) -> List[pd.DataFrame]:
    try:
        frame = pd.read_csv(path, sep=None, engine="python")
    except Exception:
        frame = pd.read_csv(path)
    return [frame] if not frame.empty else []


def _read_pdf_tables(path: Path) -> List[pd.DataFrame]:
    frames: List[pd.DataFrame] = []
    try:
        with path.open("rb") as handle:
            signature = handle.read(4)
        if signature != b"%PDF":
            LOGGER.warning("Skipping non-PDF content with .pdf extension: %s", path)
            return []
    except Exception as exc:
        LOGGER.warning("Failed to read PDF bytes %s: %s", path, exc)
        return []

    table_settings_options = [
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

    try:
        with path.open("rb") as handle:
            with pdfplumber.open(handle) as pdf:
                for page in pdf.pages:
                    page_tables: List[list[list[str | None]]] = []
                    for settings in table_settings_options:
                        tables = page.extract_tables(table_settings=settings) or []
                        if tables:
                            page_tables = tables
                            break

                    for table in page_tables:
                        frame = _table_to_frame(table)
                        if frame is not None and not frame.empty:
                            frames.append(frame)
    except AttributeError as exc:
        if "bytes" in str(exc) and "name" in str(exc):
            LOGGER.warning("Skipping malformed PDF %s: %s", path, exc)
            return []
        LOGGER.warning("Skipping unreadable PDF %s: %s", path, exc)
        return []
    except Exception as exc:
        LOGGER.warning("Skipping unreadable PDF %s: %s", path, exc)
        return []
    return frames


def normalize_frame(
    frame: pd.DataFrame,
    source_file: Path,
    metadata: Optional[FileMetadata] = None,
) -> pd.DataFrame:
    """Normalize heterogeneous source frame into target schema."""
    metadata = metadata or FileMetadata()
    cleaned = normalize_columns(frame)
    cleaned = _deduplicate_columns(cleaned)
    cleaned = cleaned.dropna(axis=0, how="all").dropna(axis=1, how="all")
    if cleaned.empty:
        return pd.DataFrame(columns=TARGET_COLUMNS)

    year_col = _find_first_column(cleaned, YEAR_ALIASES)
    departement_col = _find_first_column(cleaned, DEPARTEMENT_ALIASES)
    if not departement_col:
        departement_col = _infer_geography_column(cleaned, year_col=year_col)
    indicator_col = _find_first_column(cleaned, INDICATOR_ALIASES)
    value_col = _find_first_column(cleaned, VALUE_ALIASES)

    normalized = _reshape_to_long(
        cleaned=cleaned,
        year_col=year_col,
        geography_col=departement_col,
        indicator_col=indicator_col,
        value_col=value_col,
    )

    normalized["year"] = _coerce_year_series(normalized.get("year"))
    if normalized["year"].isna().all():
        normalized["year"] = metadata.year or infer_year_from_name(source_file)

    if "departement" not in normalized.columns:
        normalized["departement"] = pd.NA
    if normalized["departement"].isna().all() and metadata.region:
        normalized["departement"] = metadata.region

    normalized["indicator_name"] = normalized.get("indicator_name", pd.Series([pd.NA] * len(normalized))).fillna(
        metadata.dataset_type
    )

    normalized["value"] = _coerce_numeric_series(normalized.get("value"))
    normalized = normalized.dropna(subset=["value"], how="all")
    normalized = append_source_file(normalized, source_file)

    for column in TARGET_COLUMNS:
        if column not in normalized.columns:
            normalized[column] = pd.NA
    return normalized[TARGET_COLUMNS]


def normalize_file(path: Path, metadata: Optional[FileMetadata] = None) -> List[pd.DataFrame]:
    frames = load_file_frames(path)
    normalized_frames: List[pd.DataFrame] = []
    for frame in frames:
        normalized = normalize_frame(frame, source_file=path, metadata=metadata)
        if not normalized.empty:
            normalized_frames.append(normalized)
    return normalized_frames


def normalize_files(paths: Iterable[Path], metadata_map: Optional[dict[Path, FileMetadata]] = None) -> List[pd.DataFrame]:
    results: List[pd.DataFrame] = []
    metadata_map = metadata_map or {}
    for path in paths:
        metadata = metadata_map.get(path)
        results.extend(normalize_file(path, metadata=metadata))
    return results


def _find_first_column(df: pd.DataFrame, aliases: Iterable[str]) -> Optional[str]:
    alias_set = {normalize_columns(pd.DataFrame(columns=[alias])).columns[0] for alias in aliases}
    for column in df.columns:
        if column in alias_set:
            return column
    return None


def _reshape_to_long(
    cleaned: pd.DataFrame,
    year_col: Optional[str],
    geography_col: Optional[str],
    indicator_col: Optional[str],
    value_col: Optional[str],
) -> pd.DataFrame:
    base = pd.DataFrame(index=cleaned.index)

    if year_col:
        base["year"] = cleaned[year_col]
    if geography_col:
        base["departement"] = cleaned[geography_col]

    if value_col:
        base["value"] = cleaned[value_col]
        if indicator_col:
            base["indicator_name"] = cleaned[indicator_col]
        else:
            base["indicator_name"] = value_col
        return base

    numeric_columns = _detect_numeric_columns(cleaned)

    if len(numeric_columns) == 1:
        numeric_col = numeric_columns[0]
        base["value"] = cleaned[numeric_col]
        if indicator_col:
            base["indicator_name"] = cleaned[indicator_col]
        else:
            base["indicator_name"] = numeric_col
        return base

    if len(numeric_columns) > 1:
        id_vars = [col for col in [year_col, geography_col] if col]
        melted = cleaned.melt(id_vars=id_vars, value_vars=numeric_columns, var_name="indicator_name", value_name="value")
        renamed = pd.DataFrame()
        if year_col:
            renamed["year"] = melted[year_col]
        if geography_col:
            renamed["departement"] = melted[geography_col]
        renamed["indicator_name"] = melted["indicator_name"]
        renamed["value"] = melted["value"]
        return renamed

    # Last fallback for unstructured tables.
    base["indicator_name"] = cleaned.columns[0]
    base["value"] = pd.to_numeric(cleaned.iloc[:, 0], errors="coerce")
    return base


def _coerce_year_series(series: Optional[pd.Series]) -> pd.Series:
    if series is None:
        return pd.Series(dtype="Int64")
    numeric = pd.to_numeric(series, errors="coerce")
    return numeric.astype("Int64")


def _detect_numeric_columns(df: pd.DataFrame) -> List[str]:
    candidates: List[str] = []
    for column in df.columns:
        converted = _coerce_numeric_series(df[column])
        ratio = converted.notna().mean() if len(converted) else 0
        if ratio >= 0.6:
            candidates.append(column)
    return candidates


def _deduplicate_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure each column label is unique after normalization."""
    counts: dict[str, int] = {}
    new_columns: List[str] = []
    for col in [str(c) for c in df.columns]:
        idx = counts.get(col, 0)
        if idx == 0:
            new_columns.append(col)
        else:
            new_columns.append(f"{col}_{idx}")
        counts[col] = idx + 1
    deduped = df.copy()
    deduped.columns = new_columns
    return deduped


def _table_to_frame(table: list[list[str | None]]) -> Optional[pd.DataFrame]:
    if not table or len(table) < 2:
        return None
    header = [(_normalize_cell_text(col) or f"col_{idx}") for idx, col in enumerate(table[0])]
    rows = [[_normalize_cell_text(cell) for cell in row] for row in table[1:]]
    frame = pd.DataFrame(rows, columns=header)
    frame = frame.dropna(axis=1, how="all").dropna(axis=0, how="all")
    return frame if not frame.empty else None


def _normalize_cell_text(value: object) -> Optional[str]:
    if value is None:
        return None
    text = str(value).replace("\n", " ").replace(NON_BREAKING_SPACE, " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _coerce_numeric_series(series: Optional[pd.Series]) -> pd.Series:
    if series is None:
        return pd.Series(dtype="float64")
    prepared = (
        series.astype(str)
        .str.replace(NON_BREAKING_SPACE, "", regex=False)
        .str.replace(" ", "", regex=False)
        .str.replace(",", ".", regex=False)
        .str.replace(r"[^0-9\.\-]", "", regex=True)
    )
    return pd.to_numeric(prepared, errors="coerce")


def _infer_geography_column(df: pd.DataFrame, year_col: Optional[str]) -> Optional[str]:
    for column in df.columns:
        if column == year_col:
            continue
        as_text = df[column].astype(str).str.strip()
        text_ratio = (as_text != "").mean()
        numeric_ratio = _coerce_numeric_series(df[column]).notna().mean()
        if text_ratio >= 0.7 and numeric_ratio <= 0.4:
            return column
    return None
