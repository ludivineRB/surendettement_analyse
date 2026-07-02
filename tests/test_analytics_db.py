import sqlite3
from pathlib import Path

import pandas as pd

from src.storage.analytics_db import build_analytics_database


def test_build_analytics_database_creates_facts_dimensions_and_views(tmp_path: Path):
    bdf_path = tmp_path / "bdf.csv"
    insee_path = tmp_path / "insee.csv"
    sur_path = tmp_path / "surendettement.csv"
    metadata_path = tmp_path / "meta.csv"
    output_db = tmp_path / "analytics.db"

    pd.DataFrame(
        [
            {
                "reference_period": "2025-08",
                "reference_year": 2025,
                "reference_month_number": 8,
                "region": "Ile de France",
                "departement_code": "75",
                "departement_name": "Paris",
                "indicator_code": "total",
                "indicator_name": "TOTAL",
                "indicator_group": "total",
                "indicator_order": 11,
                "unit": "milliards_euros",
                "value": 568.6,
                "source_file": "bdf.pdf",
                "page_number": 1,
                "pipeline_version": "test",
            }
        ]
    ).to_csv(bdf_path, index=False)
    pd.DataFrame(
        [
            {
                "reference_year": 2026,
                "geo_level": "DEP",
                "departement_code": "75",
                "departement_name": None,
                "indicator_code": "P22_POP",
                "indicator_name": "Population",
                "indicator_group": "démographie",
                "aggregation_rule": "sum",
                "value": 2_100_000,
                "source_dataset": "insee_base_dossier_complet",
                "pipeline_version": "test",
            }
        ]
    ).to_csv(insee_path, index=False)
    pd.DataFrame(
        [
            {
                "year": 2025,
                "departement": "75",
                "indicator_name": "dossiers",
                "value": 123,
                "source_file": "sur.pdf",
            }
        ]
    ).to_csv(sur_path, index=False)
    pd.DataFrame(
        [
            {
                "COD_VAR": "P22_POP",
                "LIB_VAR": "Population en 2022",
                "LIB_VAR_LONG": "Population totale en 2022",
                "COD_MOD": "",
                "LIB_MOD": "",
                "TYPE_VAR": "NUM",
                "LONG_VAR": "16",
                "THEME": "Démographie",
                "SOURCE": "INSEE",
            }
        ]
    ).to_csv(metadata_path, sep=";", index=False)

    summary = build_analytics_database(
        bdf_curated_path=bdf_path,
        insee_macro_path=insee_path,
        surendettement_path=sur_path,
        insee_metadata_path=metadata_path,
        output_db=output_db,
    )

    assert summary == {
        "departments": 1,
        "indicators": 3,
        "surendettement_rows": 1,
        "bdf_rows": 1,
        "insee_rows": 1,
    }
    with sqlite3.connect(output_db) as connection:
        views = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='view'"
            ).fetchall()
        }
        assert "v_bdf_total_deposits" in views
        assert "v_surendettement_with_insee_macro" in views
        joined = connection.execute(
            "SELECT bdf_total_deposits_value, macro_indicator_code, macro_value "
            "FROM v_bdf_total_deposits_with_insee_macro"
        ).fetchone()
        sur_joined = connection.execute(
            "SELECT surendettement_value, macro_indicator_name, macro_value "
            "FROM v_surendettement_with_insee_macro"
        ).fetchone()
    assert joined == (568.6, "P22_POP", 2_100_000.0)
    assert sur_joined == (123.0, "Population totale en 2022", 2_100_000.0)
