from src.statinfo_bi_pipeline import _extract_monthly_publication_links, _extract_publication_pdf_url


def test_extract_monthly_publication_links_keeps_only_target_pages():
    html = """
    <html><body>
      <a href="/fr/statistiques/monnaie/depots-dans-les-regions-francaises-2026-01">Janvier 2026</a>
      <a href="/fr/statistiques/monnaie/depots-dans-les-regions-francaises-2025-12">Decembre 2025</a>
      <a href="/fr/statistiques/monnaie/autre-publication-2026-01">Autre publication</a>
    </body></html>
    """

    links = _extract_monthly_publication_links(
        listing_html=html,
        base_url="https://www.banque-france.fr/fr/publications-et-statistiques/statistiques",
    )

    assert links == [
        "https://www.banque-france.fr/fr/statistiques/monnaie/depots-dans-les-regions-francaises-2026-01",
        "https://www.banque-france.fr/fr/statistiques/monnaie/depots-dans-les-regions-francaises-2025-12",
    ]


def test_extract_monthly_publication_links_finds_links_inside_escaped_json():
    html = r'''
    <script>
      window.__DATA__ = {
        "latest": "\/fr\/statistiques\/monnaie\/depots-dans-les-regions-francaises-2026-02",
        "older": "\/fr\/statistiques\/monnaie\/depots-dans-les-regions-francaises-2026-01"
      };
    </script>
    '''

    links = _extract_monthly_publication_links(
        listing_html=html,
        base_url="https://www.banque-france.fr/fr/publications-et-statistiques/statistiques",
    )

    assert links == [
        "https://www.banque-france.fr/fr/statistiques/monnaie/depots-dans-les-regions-francaises-2026-02",
        "https://www.banque-france.fr/fr/statistiques/monnaie/depots-dans-les-regions-francaises-2026-01",
    ]


def test_extract_publication_pdf_url_prioritizes_target_pdf():
    html = """
    <html><body>
      <a href="/system/files/2026-02/notice_methodologique.pdf">Notice</a>
      <a href="/system/files/2026-02/FR_Stat_Info_Depots_Regions_2026_01.pdf">PDF principal</a>
    </body></html>
    """

    pdf_url = _extract_publication_pdf_url(
        publication_html=html,
        base_url="https://www.banque-france.fr/fr/statistiques/monnaie/depots-dans-les-regions-francaises-2026-01",
    )

    assert (
        pdf_url
        == "https://www.banque-france.fr/system/files/2026-02/FR_Stat_Info_Depots_Regions_2026_01.pdf"
    )


def test_extract_publication_pdf_url_finds_pdf_inside_escaped_json():
    html = r'''
    <script>
      window.__DATA__ = {
        "pdf": "\/system\/files\/2026-03\/FR_Stat_Info_Depots_Regions_2026_02.pdf"
      };
    </script>
    '''

    pdf_url = _extract_publication_pdf_url(
        publication_html=html,
        base_url="https://www.banque-france.fr/fr/statistiques/monnaie/depots-dans-les-regions-francaises-2026-02",
    )

    assert pdf_url == "https://www.banque-france.fr/system/files/2026-03/FR_Stat_Info_Depots_Regions_2026_02.pdf"
