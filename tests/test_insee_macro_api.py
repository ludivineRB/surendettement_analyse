from src.insee_macro_api import build_donnees_locales_url, parse_donnees_locales_xml


def test_build_donnees_locales_url_for_department():
    url = build_donnees_locales_url(
        dataset="geo-SEXE-DIPL_19@GEO2023RP2020",
        geo_level="dep",
        geo_code="75",
        modalities="all.all",
    )

    assert (
        url
        == "https://api.insee.fr/donnees-locales/donnees/geo-SEXE-DIPL_19@GEO2023RP2020/DEP-75.all.all"
    )


def test_parse_donnees_locales_xml_extracts_cells():
    xml_text = """<?xml version="1.0" encoding="UTF-8"?>
    <Donnees>
      <Croisement>
        <JeuDonnees code="GEO2023RP2020">
          <Annee>2020</Annee>
          <Libelle>Recensement de la population 2020</Libelle>
          <Source>Recensement de la population</Source>
        </JeuDonnees>
      </Croisement>
      <Variable code="SEXE">
        <Libelle>Sexe</Libelle>
        <Modalite code="ENS" variable=""><Libelle>Ensemble</Libelle></Modalite>
      </Variable>
      <Variable code="DIPL_19">
        <Libelle>Diplôme</Libelle>
        <Modalite code="ENS" variable=""><Libelle>Ensemble</Libelle></Modalite>
      </Variable>
      <Cellule>
        <Zone codgeo="75" nivgeo="DEP"/>
        <Mesure code="POP">Population</Mesure>
        <Modalite code="ENS" variable="SEXE"/>
        <Modalite code="ENS" variable="DIPL_19"/>
        <Valeur>1563174.78939</Valeur>
      </Cellule>
    </Donnees>
    """

    parsed = parse_donnees_locales_xml(xml_text, source_url="https://api.insee.fr/example")

    assert len(parsed) == 1
    assert parsed.loc[0, "api_source"] == "insee_donnees_locales"
    assert parsed.loc[0, "dataset_code"] == "GEO2023RP2020"
    assert parsed.loc[0, "geo_level"] == "DEP"
    assert parsed.loc[0, "departement_code"] == "75"
    assert parsed.loc[0, "measure_code"] == "POP"
    assert parsed.loc[0, "value"] == 1563174.78939
