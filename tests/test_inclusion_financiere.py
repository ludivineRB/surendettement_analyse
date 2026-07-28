from pathlib import Path

import pytest
import requests

from src.inclusion_financiere import (
    DownloadedDocument,
    InclusionFinancialPipeline,
    PublicationMetadata,
    QualityReport,
    build_metadata,
    build_fallback_publication_urls,
    extract_observations_from_text,
    extract_publication_links,
    idempotence_key,
    month_to_number,
    normalize_region,
    parse_french_number,
    parse_period,
    validate_pdf_response,
)
from src.storage.database import init_db
from src.utils.config import PipelineConfig


HTML = """
<html>
  <head>
    <link rel="canonical" href="https://www.banque-france.fr/fr/publications-et-statistiques/statistiques/barometre-mensuel-de-linclusion-financiere-corse-juin-2026">
    <meta property="article:published_time" content="2026-07-16T09:00:00+02:00">
  </head>
  <body>
    <h1>Baromètre mensuel de l’inclusion financière : Corse - juin 2026</h1>
    <p>Mise en ligne le 16 Juillet 2026</p>
    <a href="/system/files/2026-07/barometre-inclusion-financiere-corse-juin-2026.pdf">PDF principal (1,2 Mo)</a>
    <p>Mise à jour le 17 Juillet 2026</p>
  </body>
</html>
"""


def test_region_month_period_and_number_normalization():
    assert normalize_region("Île-de-France") == ("11", "Île-de-France", "ile-de-france")
    assert month_to_number("février") == "02"
    assert parse_period("juin", 2026) == "2026-06"
    assert parse_french_number("1\u00a0234,5 %") == 1234.5
    assert parse_french_number("(12,3)") == -12.3
    assert parse_french_number("n.d.") is None


def test_extract_publication_links_from_listing_fixture():
    html = """
    <a href="/fr/publications-et-statistiques/statistiques/barometre-mensuel-de-linclusion-financiere-corse-juin-2026">Corse</a>
    <a href="/fr/autre-publication">Autre</a>
    """
    links = extract_publication_links(html, "https://www.banque-france.fr/fr/publications-et-statistiques/statistiques")
    assert links == [
        "https://www.banque-france.fr/fr/publications-et-statistiques/statistiques/barometre-mensuel-de-linclusion-financiere-corse-juin-2026"
    ]


def test_fallback_urls_are_parameterized_by_period_and_region():
    urls = build_fallback_publication_urls("2026-06", "2026-07", {"corse"})
    assert urls == [
        "https://www.banque-france.fr/fr/publications-et-statistiques/statistiques/barometre-mensuel-de-linclusion-financiere-corse-juin-2026",
        "https://www.banque-france.fr/fr/publications-et-statistiques/statistiques/barometre-mensuel-de-linclusion-financiere-corse-juillet-2026",
    ]


def test_discovery_falls_back_when_listing_fails(monkeypatch):
    pipeline = InclusionFinancialPipeline()
    monkeypatch.setattr(pipeline, "_fetch_html", lambda *args, **kwargs: (_ for _ in ()).throw(requests.ReadTimeout("slow")))
    monkeypatch.setattr(pipeline, "_discover_from_sitemap", lambda: [])

    urls = pipeline._discover_publication_urls("2026-06", "2026-06", {"corse"})

    assert urls == [
        "https://www.banque-france.fr/fr/publications-et-statistiques/statistiques/barometre-mensuel-de-linclusion-financiere-corse-juin-2026"
    ]


def test_build_metadata_extracts_pdf_from_dom():
    meta = build_metadata(HTML, "https://www.banque-france.fr/fr/source")
    assert meta.region_code == "94"
    assert meta.reference_period == "2026-06"
    assert meta.pdf_url == "https://www.banque-france.fr/system/files/2026-07/barometre-inclusion-financiere-corse-juin-2026.pdf"
    assert meta.pdf_filename == "barometre-inclusion-financiere-corse-juin-2026.pdf"
    assert meta.announced_size == "1,2 Mo"
    assert meta.publication_date == "2026-07-16"
    assert meta.updated_date == "2026-07-17"


def test_validate_pdf_response_rejects_html_as_pdf():
    validate_pdf_response(200, "application/pdf", b"%PDF-" + (b"x" * 600))
    with pytest.raises(ValueError, match="non PDF MIME"):
        validate_pdf_response(200, "text/html", b"%PDF-" + (b"x" * 600))
    with pytest.raises(ValueError, match="non PDF signature"):
        validate_pdf_response(200, "application/pdf", b"<html>" + (b"x" * 600))


def test_extract_observations_from_text_and_idempotence():
    meta = PublicationMetadata(
        page_url="https://www.banque-france.fr/fr/page",
        title="Baromètre mensuel de l’inclusion financière : Corse - juin 2026",
        region_code="94",
        region_name="Corse",
        region_slug="corse",
        reference_month="06",
        reference_year=2026,
        reference_period="2026-06",
        publication_date=None,
        updated_date=None,
        pdf_url="https://www.banque-france.fr/file.pdf",
        pdf_filename="file.pdf",
        announced_size=None,
        discovered_at="2026-07-16T00:00:00+00:00",
        last_checked_at="2026-07-16T00:00:00+00:00",
    )
    doc = DownloadedDocument(meta, Path("file.pdf"), "abc", 1000, None, None, "2026-07-16T00:00:00+00:00")
    rows = extract_observations_from_text("Dossiers de surendettement déposés 123 Droit au compte 45", doc, 1)
    assert [row["indicator_code"] for row in rows] == [
        "surendettement_dossiers_deposes",
        "droit_compte_designations",
    ]
    assert rows[0]["value_numeric"] == 123
    assert idempotence_key("abc", "x") == idempotence_key("abc", "x")


class FakeResponse:
    def __init__(self, status_code=200, content=b"", headers=None, text="", url="https://www.banque-france.fr/x"):
        self.status_code = status_code
        self.content = content
        self.headers = headers or {"Content-Type": "application/pdf"}
        self.text = text
        self.url = url

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError("temporary")


def test_download_retries_and_rejects_fake_pdf(monkeypatch, tmp_path):
    config = PipelineConfig()
    config.output_raw_dir = tmp_path
    pipeline = InclusionFinancialPipeline(config=config, storage_root=tmp_path, max_retries=2)
    meta = build_metadata(HTML, "https://www.banque-france.fr/fr/source")
    calls = {"count": 0}

    def fake_get(url, timeout, headers=None):
        calls["count"] += 1
        if calls["count"] == 1:
            raise requests.ConnectionError("temporary")
        return FakeResponse(content=b"<html>" + (b"x" * 600), headers={"Content-Type": "text/html"})

    monkeypatch.setattr(pipeline.session, "get", fake_get)
    with pytest.raises(Exception):
        pipeline.download(meta)
    assert calls["count"] == 2


def test_load_is_idempotent(monkeypatch, tmp_path):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    init_db()
    pipeline = InclusionFinancialPipeline(storage_root=tmp_path, output_jsonl=tmp_path / "out.jsonl")
    meta = build_metadata(HTML, "https://www.banque-france.fr/fr/source")
    doc = DownloadedDocument(meta, tmp_path / "abc.pdf", "a" * 64, 1024, "etag", "last", "2026-07-16T00:00:00+00:00")
    rows = extract_observations_from_text("Dossiers de surendettement déposés 123", doc, 1)

    assert pipeline.load([(doc, rows, QualityReport())]) == (1, 1)
    assert pipeline.load([(doc, rows, QualityReport())]) == (0, 0)
