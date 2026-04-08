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
REGION_ALIASES = ("region", "région", "territoire", "departement", "département")
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

TARGET_COLUMNS = ["year", "region", "indicator_name", "value", "source_file"]
LOGGER = get_logger(__name__)


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
    workbook = pd.read_excel(path, sheet_name=None)
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
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables() or []
                for table in tables:
                    if not table or len(table) < 2:
                        continue
                    header = table[0]
                    rows = table[1:]
                    frame = pd.DataFrame(rows, columns=header)
                    if not frame.empty:
                        frames.append(frame)
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
    region_col = _find_first_column(cleaned, REGION_ALIASES)
    indicator_col = _find_first_column(cleaned, INDICATOR_ALIASES)
    value_col = _find_first_column(cleaned, VALUE_ALIASES)

    normalized = _reshape_to_long(
        cleaned=cleaned,
        year_col=year_col,
        region_col=region_col,
        indicator_col=indicator_col,
        value_col=value_col,
    )

    normalized["year"] = _coerce_year_series(normalized.get("year"))
    if normalized["year"].isna().all():
        normalized["year"] = metadata.year or infer_year_from_name(source_file)

    if "region" not in normalized.columns:
        normalized["region"] = pd.NA
    if normalized["region"].isna().all() and metadata.region:
        normalized["region"] = metadata.region

    normalized["indicator_name"] = normalized.get("indicator_name", pd.Series([pd.NA] * len(normalized))).fillna(
        metadata.dataset_type
    )

    normalized["value"] = pd.to_numeric(normalized.get("value"), errors="coerce")
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
    region_col: Optional[str],
    indicator_col: Optional[str],
    value_col: Optional[str],
) -> pd.DataFrame:
    base = pd.DataFrame(index=cleaned.index)

    if year_col:
        base["year"] = cleaned[year_col]
    if region_col:
        base["region"] = cleaned[region_col]

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
        id_vars = [col for col in [year_col, region_col] if col]
        melted = cleaned.melt(id_vars=id_vars, value_vars=numeric_columns, var_name="indicator_name", value_name="value")
        renamed = pd.DataFrame()
        if year_col:
            renamed["year"] = melted[year_col]
        if region_col:
            renamed["region"] = melted[region_col]
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
        converted = pd.to_numeric(df[column], errors="coerce")
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
