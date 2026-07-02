from pathlib import Path

import pandas as pd
import pytest

from src.statinfo_bi_quality import EXPECTED_DEPARTMENT_CODES
from src.scraper.parser import ParsedLink
from src.surendettement_pipeline import (
    SurendettementPipelineSummary,
    _crawl_and_download,
    _is_relevant_structured_link,
    parse_structured_source,
    run_surendettement_pipeline,
)


def test_parse_structured_source_accepts_national_department_file(tmp_path: Path):
    source = tmp_path / "surendettement_dossiers_2025.csv"
    pd.DataFrame(
        [
            {
                "annee": 2025,
                "mois": 1,
                "code_departement": code,
                "nom_departement": f"Departement {code}",
                "nombre_dossiers_deposes": 100 + index,
            }
            for index, code in enumerate(sorted(EXPECTED_DEPARTMENT_CODES))
        ]
    ).to_csv(source, index=False)

    result = parse_structured_source(source)

    assert len(result) == len(EXPECTED_DEPARTMENT_CODES)
    assert result["indicator_code"].unique().tolist() == ["dossiers_deposes"]
    assert result["indicator_name"].unique().tolist() == ["Nombre de dossiers déposés"]
    assert result["departement_code"].nunique() == len(EXPECTED_DEPARTMENT_CODES)


def test_parse_structured_source_rejects_pdf(tmp_path: Path):
    source = tmp_path / "surendettement_2025.pdf"
    source.write_bytes(b"%PDF fake")

    with pytest.raises(ValueError, match="Only CSV/XLSX"):
        parse_structured_source(source)


def test_run_pipeline_rejects_partial_structured_file(tmp_path: Path):
    source_dir = tmp_path / "raw"
    source_dir.mkdir()
    pd.DataFrame(
        [
            {
                "annee": 2025,
                "code_departement": "75",
                "nombre_dossiers_deposes": 123,
            }
        ]
    ).to_csv(source_dir / "partial.csv", index=False)

    output = tmp_path / "gold.csv"
    summary = run_surendettement_pipeline(skip_crawl=True, source_dir=source_dir, output_csv=output)

    assert summary.files_processed == 0
    assert summary.files_rejected == 1
    assert summary.output_rows == 0
    assert pd.read_csv(output).empty


def test_relevant_structured_link_accepts_typologie_without_filings_word():
    link = ParsedLink(
        url="https://www.banque-france.fr/fr/data/typologie-surendettement-2025.xlsx",
        text="Typologie du surendettement 2025",
        is_file=True,
        extension=".xlsx",
        relevance_score=2,
        year=2025,
        region=None,
        dataset_type="typologie",
    )

    assert _is_relevant_structured_link(link)


def test_download_all_discovered_selects_generic_structured_links(monkeypatch, tmp_path: Path):
    link = ParsedLink(
        url="https://www.banque-france.fr/fr/data/statistiques.csv",
        text="Télécharger",
        is_file=True,
        extension=".csv",
        relevance_score=0,
        year=None,
        region=None,
        dataset_type="unknown",
    )
    downloaded = tmp_path / "statistiques.csv"

    monkeypatch.setattr("src.surendettement_pipeline._crawl_structured_links", lambda summary: [link])

    class FakeDownloader:
        def __init__(self, config):
            self.config = config

        def download_file(self, link, skip_existing=True):
            return downloaded

    monkeypatch.setattr("src.surendettement_pipeline.FileDownloader", FakeDownloader)
    summary = SurendettementPipelineSummary()

    paths = _crawl_and_download(tmp_path, summary, download_all_discovered=True)

    assert paths == [downloaded]
    assert summary.files_selected_for_download == 1
    assert summary.files_downloaded == 1
