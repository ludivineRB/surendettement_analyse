from src.scraper.downloader import FileDownloader
from src.scraper.parser import ParsedLink
from src.utils.config import PipelineConfig


def test_candidate_urls_adds_espaces2_fallback():
    downloader = FileDownloader(config=PipelineConfig())
    urls = downloader._candidate_urls(
        "https://www.espaces2.banque-france.fr/system/files/report.pdf"
    )
    assert urls[0] == "https://www.espaces2.banque-france.fr/system/files/report.pdf"
    assert urls[1] == "https://espaces2.banque-france.fr/system/files/report.pdf"


def test_download_file_skips_existing_target(tmp_path):
    config = PipelineConfig()
    config.output_raw_dir = tmp_path
    downloader = FileDownloader(config=config)

    existing = tmp_path / "bdf_2025_typologie_typologie_2025.pdf"
    existing.write_bytes(b"already here")

    link = ParsedLink(
        url="https://www.banque-france.fr/system/files/typologie-2025.pdf",
        text="typologie 2025",
        is_file=True,
        extension=".pdf",
        relevance_score=1,
        year=2025,
        region=None,
        dataset_type="typologie",
    )
    path = downloader.download_file(link, skip_existing=True)
    assert path == existing


def test_build_filename_uses_url_slug_to_avoid_unknown_collisions():
    downloader = FileDownloader(config=PipelineConfig())

    link = ParsedLink(
        url="https://www.banque-france.fr/system/files/2026-04/20260217_arrete_commission_surendettement_original.pdf",
        text="Arrêté commission surendettement",
        is_file=True,
        extension=".pdf",
        relevance_score=1,
        year=2026,
        region=None,
        dataset_type="unknown",
    )

    filename = downloader.build_filename(link)
    assert filename == "bdf_2026_unknown_20260217_arrete_commission_surendettement_original.pdf"
