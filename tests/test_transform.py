import pandas as pd

from src.processing.transform import build_unified_frame


def test_build_unified_frame_adds_missing_columns():
    frames = [pd.DataFrame([{"year": 2025, "indicator_name": "dossiers", "value": 10}])]
    result = build_unified_frame(frames)
    assert set(result.columns) == {"year", "region", "indicator_name", "value", "source_file"}
    assert result.loc[0, "year"] == 2025

