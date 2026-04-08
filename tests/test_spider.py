from src.scraper.spider import BanqueFranceSpider
from src.utils.config import PipelineConfig


def test_spider_crawl_discovers_file_links(monkeypatch):
    config = PipelineConfig(
        start_urls=["https://www.banque-france.fr/fr/start"],
        max_depth=2,
        max_pages=10,
    )
    spider = BanqueFranceSpider(config=config)

    pages = {
        "https://www.banque-france.fr/fr/start": """
            <a href='/fr/surendettement'>Surendettement</a>
        """,
        "https://www.banque-france.fr/fr/surendettement": """
            <a href='/fr/data/typologie-2024.xlsx'>Télécharger</a>
        """,
    }

    def fake_fetch(url):
        return pages.get(url)

    monkeypatch.setattr(spider, "_fetch_page", fake_fetch)
    result = spider.crawl()

    assert "https://www.banque-france.fr/fr/surendettement" in result.pages
    assert any(item.url.endswith("typologie-2024.xlsx") for item in result.files)


def test_spider_filters_irrelevant_file_links(monkeypatch):
    config = PipelineConfig(
        start_urls=["https://www.banque-france.fr/fr/start"],
        max_depth=1,
        max_pages=10,
    )
    spider = BanqueFranceSpider(config=config)

    pages = {
        "https://www.banque-france.fr/fr/start": """
            <a href='/fr/autre-page'>Actualités générales</a>
            <a href='/fr/surendettement'>Surendettement</a>
        """,
        "https://www.banque-france.fr/fr/autre-page": """
            <a href='/fr/data/g20-2025.pdf'>G20 document</a>
        """,
        "https://www.banque-france.fr/fr/surendettement": """
            <a href='/fr/data/typologie-2025.xlsx'>Typologie 2025</a>
        """,
    }

    def fake_fetch(url):
        return pages.get(url)

    monkeypatch.setattr(spider, "_fetch_page", fake_fetch)
    result = spider.crawl()
    urls = [item.url for item in result.files]

    assert any(url.endswith("typologie-2025.xlsx") for url in urls)
    assert not any(url.endswith("g20-2025.pdf") for url in urls)


def test_spider_falls_back_to_base_url_when_custom_seed_unavailable(monkeypatch):
    config = PipelineConfig(
        base_url="https://www.banque-france.fr/fr",
        start_urls=["https://www.banque-france.fr/fr/invalid-seed"],
        max_depth=1,
        max_pages=10,
    )
    spider = BanqueFranceSpider(config=config)

    pages = {
        "https://www.banque-france.fr/fr/invalid-seed": None,
        "https://www.banque-france.fr/fr": """
            <a href='/fr/surendettement'>Surendettement</a>
        """,
        "https://www.banque-france.fr/fr/surendettement": """
            <a href='/fr/data/typologie-2024.xlsx'>Télécharger</a>
        """,
    }

    def fake_fetch(url):
        return pages.get(url)

    monkeypatch.setattr(spider, "_fetch_page", fake_fetch)
    result = spider.crawl()

    assert "https://www.banque-france.fr/fr" in result.pages
    assert any(item.url.endswith("typologie-2024.xlsx") for item in result.files)
