from src.scraper.downloader import FileDownloader
from src.utils.config import PipelineConfig


def test_candidate_urls_adds_espaces2_fallback():
    downloader = FileDownloader(config=PipelineConfig())
    urls = downloader._candidate_urls(
        "https://www.espaces2.banque-france.fr/system/files/report.pdf"
    )
    assert urls[0] == "https://www.espaces2.banque-france.fr/system/files/report.pdf"
    assert urls[1] == "https://espaces2.banque-france.fr/system/files/report.pdf"

