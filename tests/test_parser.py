from src.scraper.parser import parse_page_links


def test_parse_page_links_detects_supported_files_and_metadata():
    html = """
    <html><body>
      <a href="/fr/statistiques/surendettement-2025.xlsx">Typologie 2025</a>
      <a href="/fr/article">Statistiques régionales</a>
    </body></html>
    """
    links = parse_page_links(
        html=html,
        base_url="https://www.banque-france.fr/fr",
        keywords=["surendettement", "statistiques", "typologie"],
        supported_extensions=[".xlsx", ".csv", ".pdf"],
    )
    assert len(links) == 2
    file_link = next(link for link in links if link.is_file)
    assert file_link.extension == ".xlsx"
    assert file_link.year == 2025
    assert file_link.dataset_type == "typologie"

