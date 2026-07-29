import pandas as pd

from src.risk_score.validation import _optional_float, _spearman


def test_optional_float_handles_missing_values():
    assert _optional_float(float("nan")) is None
    assert _optional_float(0.75) == 0.75
    assert _spearman(pd.Series([1, 2, 3]), pd.Series([10, 20, 30])) == 1.0
