from pathlib import Path

import pandas as pd

from src.processing.ingest import FileMetadata, normalize_frame


def test_normalize_frame_from_wide_table():
    frame = pd.DataFrame(
        {
            "Année": [2024, 2025],
            "Région": ["ile-de-france", "normandie"],
            "dossiers_deposes": [100, 120],
            "dossiers_recevables": [90, 110],
        }
    )

    result = normalize_frame(
        frame=frame,
        source_file=Path("bdf_2025_statistiques.xlsx"),
        metadata=FileMetadata(dataset_type="statistiques"),
    )

    assert set(result.columns) == {"year", "region", "indicator_name", "value", "source_file"}
    assert len(result) == 4
    assert result["value"].notna().all()
    assert set(result["indicator_name"].unique()) == {"dossiers_deposes", "dossiers_recevables"}


def test_normalize_frame_handles_duplicate_normalized_columns():
    frame = pd.DataFrame(
        {
            "Valeur": [10, 20],
            "valeur": [11, 21],
            "Année": [2024, 2025],
        }
    )
    result = normalize_frame(
        frame=frame,
        source_file=Path("bdf_2025_statistiques.csv"),
        metadata=FileMetadata(dataset_type="statistiques"),
    )
    assert not result.empty
    assert set(result.columns) == {"year", "region", "indicator_name", "value", "source_file"}
