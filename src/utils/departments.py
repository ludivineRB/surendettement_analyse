"""Department code normalization helpers."""

from __future__ import annotations

import pandas as pd


def normalize_department_code(value: object) -> str | None:
    """Return a French department code suitable for joins and maps."""
    if value is None or pd.isna(value):
        return None

    code = str(value).strip().upper().replace(".0", "")
    if not code:
        return None

    if code in {"2A", "2B"}:
        return code
    if code.isdigit():
        return code.zfill(2)
    return code


def add_department_code(df: pd.DataFrame, source_column: str) -> pd.DataFrame:
    """Add a normalized departement_code column from an existing column."""
    output = df.copy()
    output["departement_code"] = output[source_column].map(normalize_department_code)
    return output
