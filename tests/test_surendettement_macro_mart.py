from pathlib import Path

import pandas as pd

from src.marts.build_surendettement_macro import build_surendettement_macro_mart


def test_build_surendettement_macro_mart_joins_total_deposits_with_macro(tmp_path: Path):
    bdf_path = tmp_path / "bdf.csv"
    macro_path = tmp_path / "macro.csv"
    output_path = tmp_path / "mart.csv"
    pd.DataFrame(
        [
            {
                "reference_period": "2025-08",
                "reference_year": 2025,
                "reference_month_number": 8,
                "departement_code": "75",
                "departement_name": "Paris",
                "region": "Ile de France",
                "indicator_code": "total",
                "value": 568.6,
            },
            {
                "reference_period": "2025-08",
                "reference_year": 2025,
                "reference_month_number": 8,
                "departement_code": "75",
                "departement_name": "Paris",
                "region": "Ile de France",
                "indicator_code": "pel",
                "value": 10.0,
            },
        ]
    ).to_csv(bdf_path, index=False)
    pd.DataFrame(
        [
            {
                "reference_year": 2026,
                "departement_code": "75",
                "indicator_code": "P20_POP",
                "value": 2_100_000,
            }
        ]
    ).to_csv(macro_path, index=False)

    mart = build_surendettement_macro_mart(
        bdf_curated_path=bdf_path,
        insee_macro_path=macro_path,
        output_path=output_path,
    )

    assert len(mart) == 1
    assert mart.loc[0, "bdf_total_deposits_value"] == 568.6
    assert mart.loc[0, "macro_P20_POP"] == 2_100_000
    assert mart.loc[0, "macro_reference_year"] == 2026
    assert output_path.exists()
