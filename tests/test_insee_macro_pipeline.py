from pathlib import Path

import pandas as pd

import src.insee_macro.pipeline as pipeline


def _isolate_pipeline_roots(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "RAW_ROOT", tmp_path / "raw")
    monkeypatch.setattr(pipeline, "SILVER_ROOT", tmp_path / "silver")
    monkeypatch.setattr(pipeline, "GOLD_ROOT", tmp_path / "gold")


def test_discover_dossier_complet_downloads_keeps_dataset_links():
    html = """
    <a href="/fr/statistiques/fichier/5359146/dossier_complet.csv">current</a>
    <a href="/fr/statistiques/fichier/5359146/dossier_complet_31_12_2025.zip">2025</a>
    <a href="/fr/statistiques/fichier/5359146/notice.pdf">notice</a>
    """

    candidates = pipeline.discover_dossier_complet_downloads(html)

    assert [candidate.filename for candidate in candidates] == [
        "dossier_complet.csv",
        "dossier_complet_31_12_2025.zip",
    ]
    assert candidates[1].year == 2025


def test_build_communes_long_filters_dom_and_keeps_metropolitan_departments(tmp_path: Path, monkeypatch):
    _isolate_pipeline_roots(tmp_path, monkeypatch)
    source_csv = tmp_path / "dossier_complet.csv"
    source_csv.write_text(
        "\n".join(
            [
                "CODGEO;LIBGEO;DEP;REG;P20_POP;TX_CHOM",
                "01001;Commune A;01;84;100;5.5",
                "75056;Paris;75;11;200;7.0",
                "97101;Commune DOM;971;01;300;8.0",
            ]
        ),
        encoding="utf-8",
    )

    communes = pipeline.build_communes_long(2099, source_csv=source_csv, chunksize=2)

    assert set(communes["departement_code"]) == {"01", "75"}
    assert set(communes["indicator_code"]) == {"P20_POP", "TX_CHOM"}
    assert len(communes) == 4


def test_aggregate_departements_uses_sum_and_mean_rules(tmp_path: Path, monkeypatch):
    _isolate_pipeline_roots(tmp_path, monkeypatch)
    source_csv = tmp_path / "dossier_complet.csv"
    source_csv.write_text(
        "\n".join(
            [
                "CODGEO;LIBGEO;DEP;REG;P20_POP;TX_CHOM",
                "01001;Commune A;01;84;100;5.0",
                "01002;Commune B;01;84;200;7.0",
            ]
        ),
        encoding="utf-8",
    )
    pipeline.build_communes_long(2098, source_csv=source_csv, chunksize=10)

    departements = pipeline.aggregate_departements(2098)

    pop = departements.loc[departements["indicator_code"] == "P20_POP", "value"].iloc[0]
    tx_chom = departements.loc[departements["indicator_code"] == "TX_CHOM", "value"].iloc[0]
    assert pop == 300
    assert tx_chom == 6
    assert (pipeline.PipelinePaths.for_year(2098).departements_long_csv).exists()


def test_extract_raw_source_reports_incomplete_zip(tmp_path: Path, monkeypatch):
    _isolate_pipeline_roots(tmp_path, monkeypatch)
    raw_dir = pipeline.PipelinePaths.for_year(2097).raw_dir
    raw_dir.mkdir(parents=True)
    bad_zip = raw_dir / "dossier_complet.zip"
    bad_zip.write_bytes(b"PK\x03\x04not-complete")

    try:
        pipeline.extract_raw_source(2097)
    except Exception as exc:
        assert "not a complete ZIP archive" in str(exc)
    else:
        raise AssertionError("Expected incomplete ZIP to fail explicitly")
