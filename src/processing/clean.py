"""Data cleaning routines for raw surendettement datasets."""

from __future__ import annotations

import pandas as pd


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize dataframe column names to snake_case."""
    cleaned = df.copy()
    cleaned.columns = (
        cleaned.columns.astype(str).str.strip().str.lower().str.replace(r"[^a-z0-9]+", "_", regex=True).str.strip("_")
    )
    return cleaned


def coerce_value_column(df: pd.DataFrame, column: str = "value") -> pd.DataFrame:
    """Convert selected value column to numeric when possible."""
    cleaned = df.copy()
    if column in cleaned.columns:
        cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce")
    return cleaned

