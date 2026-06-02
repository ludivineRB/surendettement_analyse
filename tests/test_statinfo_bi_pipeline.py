from src.statinfo_bi_pipeline import (
    DEPOSITS_REGION_INDICATORS,
    _extract_monthly_publication_links,
    _extract_publication_pdf_url,
    _extract_reference_period,
    _extract_rows_from_text_page,
)


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


def test_extract_rows_from_text_page_uses_stable_indicator_names():
    text = """
    Comptes Autres Livrets Livrets de Comptes Plans Comptes Bons de
    Nouvelle
    Aquitaine 76,0 57,1 9,2 15,2 3,2 0,9 18,5 0,8 29,3 0,0 210,0
    16 Charente 4,1 3,2 0,6 0,9 0,2 0,1 0,9 0,1 1,7 0,0 11,8
    """

    rows = _extract_rows_from_text_page(
        text=text,
        reference_year=2025,
        reference_month="aout",
        source_file="sample.pdf",
        page_number=2,
    )

    assert len(rows) == len(DEPOSITS_REGION_INDICATORS)
    assert [row["indicator_name"] for row in rows] == DEPOSITS_REGION_INDICATORS
    assert {row["region"] for row in rows} == {"Nouvelle Aquitaine"}
    assert {row["departement_code"] for row in rows} == {"16"}
    assert rows[-1]["indicator_name"] == "TOTAL"
    assert rows[-1]["value"] == 11.8


def test_extract_rows_from_text_page_rejoins_split_department_names():
    text = """
    Nouvelle
    Aquitaine 76,0 57,1 9,2 15,2 3,2 0,9 18,5 0,8 29,3 0,0 210,0
    17 Charente
    Maritime 7,8 6,7 1,1 1,8 0,4 0,1 2,3 0,1 2,9 0,0 23,3
    """

    rows = _extract_rows_from_text_page(
        text=text,
        reference_year=2025,
        reference_month="aout",
        source_file="sample.pdf",
        page_number=2,
    )

    assert len(rows) == len(DEPOSITS_REGION_INDICATORS)
    assert {row["departement_code"] for row in rows} == {"17"}
    assert {row["departement_name"] for row in rows} == {"Charente Maritime"}


def test_extract_rows_from_text_page_accepts_corsica_department_codes():
    text = """
    Corse 6,1 2,3 0,3 0,6 0,1 0,0 0,6 0,0 1,4 0,0 11,4
    2A Corse du Sud 2,8 1,1 0,1 0,3 0,0 0,0 0,3 0,0 0,6 0,0 5,2
    2B Haute Corse 3,3 1,2 0,1 0,3 0,1 0,0 0,3 0,0 0,8 0,0 6,2
    """

    rows = _extract_rows_from_text_page(
        text=text,
        reference_year=2025,
        reference_month="aout",
        source_file="sample.pdf",
        page_number=6,
    )

    assert len(rows) == 2 * len(DEPOSITS_REGION_INDICATORS)
    assert {row["region"] for row in rows} == {"Corse"}
    assert {row["departement_code"] for row in rows} == {"2A", "2B"}


def test_extract_reference_period_prefers_statement_date_over_publication_date():
    text = """
    Dépôts et comptes d’épargne dans les régions françaises
    23 Février 2026
    Encours des dépôts non cvs au 31 Décembre 2025* Encours en milliards d'euros
    """

    assert _extract_reference_period(text, fallback="sample_202512.pdf") == (2025, "décembre")
