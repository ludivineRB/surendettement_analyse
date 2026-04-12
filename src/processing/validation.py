"""Validation checks for cleaned and transformed datasets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import pandas as pd


@dataclass(slots=True)
class ValidationResult:
    is_valid: bool
    errors: List[str]


def validate_schema(df: pd.DataFrame) -> ValidationResult:
    expected = {"year", "departement", "indicator_name", "value", "source_file"}
    missing = sorted(expected.difference(df.columns))
    if missing:
        return ValidationResult(False, [f"Missing columns: {', '.join(missing)}"])
    return ValidationResult(True, [])


def validate_non_empty(df: pd.DataFrame) -> ValidationResult:
    if df.empty:
        return ValidationResult(False, ["Dataset is empty"])
    return ValidationResult(True, [])
