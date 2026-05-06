from pathlib import Path

import pandas as pd

from src.processing.ingest import FileMetadata, _read_pdf_tables, normalize_frame


def test_normalize_frame_from_wide_table():
    frame = pd.DataFrame(
        {
            "Année": [2024, 2025],
            "Département": ["paris", "seine-maritime"],
            "dossiers_deposes": [100, 120],
            "dossiers_recevables": [90, 110],
        }
    )

    result = normalize_frame(
        frame=frame,
        source_file=Path("bdf_2025_statistiques.xlsx"),
        metadata=FileMetadata(dataset_type="statistiques"),
    )

    assert set(result.columns) == {"year", "departement", "indicator_name", "value", "source_file"}
    assert len(result) == 4
    assert result["value"].notna().all()
    assert set(result["indicator_name"].unique()) == {"dossiers_deposes", "dossiers_recevables"}
    assert set(result["departement"].unique()) == {"paris", "seine-maritime"}


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
    assert set(result.columns) == {"year", "departement", "indicator_name", "value", "source_file"}


def test_normalize_frame_falls_back_to_region_alias_when_no_departement_column():
    frame = pd.DataFrame(
        {
            "Année": [2024],
            "Région": ["ile-de-france"],
            "dossiers_deposes": [100],
        }
    )

    result = normalize_frame(
        frame=frame,
        source_file=Path("bdf_2024_statistiques.xlsx"),
        metadata=FileMetadata(dataset_type="statistiques"),
    )

    assert set(result.columns) == {"year", "departement", "indicator_name", "value", "source_file"}
    assert result.loc[0, "departement"] == "ile-de-france"


def test_read_pdf_tables_handles_invalid_pdf(monkeypatch, tmp_path):
    pdf_file = tmp_path / "invalid.pdf"
    pdf_file.write_bytes(b"not a real pdf")

    def raise_open(*args, **kwargs):
        raise ValueError("bad pdf")

    monkeypatch.setattr("src.processing.ingest.pdfplumber.open", raise_open)
    frames = _read_pdf_tables(pdf_file)
    assert frames == []
