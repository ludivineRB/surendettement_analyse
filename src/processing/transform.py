"""Transformation functions to map source files to unified schema."""

from __future__ import annotations

from pathlib import Path
from typing import List

import pandas as pd


TARGET_COLUMNS = ["year", "departement", "indicator_name", "value", "source_file"]


def build_unified_frame(frames: List[pd.DataFrame]) -> pd.DataFrame:
    """Concatenate normalized datasets into one unified dataframe."""
    if not frames:
        return pd.DataFrame(columns=TARGET_COLUMNS)

    unified = pd.concat(frames, ignore_index=True)
    if "departement" not in unified.columns and "region" in unified.columns:
        unified["departement"] = unified["region"]
    for col in TARGET_COLUMNS:
        if col not in unified.columns:
            unified[col] = pd.NA
    return unified[TARGET_COLUMNS]


def append_source_file(df: pd.DataFrame, source_path: Path) -> pd.DataFrame:
    """Attach source file metadata to a dataframe."""
    transformed = df.copy()
    transformed["source_file"] = source_path.name
    return transformed
