from __future__ import annotations

import re
import json
import time
from defusedxml import ElementTree as ET

import pandas as pd
import requests

BASE_URL = "https://api.insee.fr/donnees-locales/donnees"

# Exemple :
# geo-SEXE-DIPL_19@GEO2023RP2020
DATASETS = [
    "geo-SEXE-DIPL_19@GEO2018RP2015",
    "geo-SEXE-DIPL_19@GEO2019RP2016",
    "geo-SEXE-DIPL_19@GEO2020RP2017",
    "geo-SEXE-DIPL_19@GEO2021RP2018",
    "geo-SEXE-DIPL_19@GEO2022RP2019",
    "geo-SEXE-DIPL_19@GEO2023RP2020",
    "geo-SEXE-DIPL_19@GEO2024RP2021",
    "geo-SEXE-DIPL_19@GEO2025RP2022",
    "geo-SEXE-DIPL_19@GEO2026RP2023",
]

MODALITIES = "all.all"

OUTPUT_FILE = (
    "data/processed/insee_macro/"
    "recensement_diplome_tous_departements.csv"
)


def get_departements() -> list[str]:
    """
    Récupère automatiquement la liste des départements.
    """

    response = requests.get(
        "https://geo.api.gouv.fr/departements",
        timeout=30
    )

    response.raise_for_status()

    departements = response.json()

    return sorted(
        [dep["code"] for dep in departements]
    )


def build_url(
    dataset: str,
    departement_code: str,
) -> str:

    return (
        f"{BASE_URL}/"
        f"{dataset}/"
        f"DEP-{departement_code}.{MODALITIES}"
    )


def fetch_xml(
    url: str,
    timeout_seconds: int = 60,
) -> str:

    response = requests.get(
        url,
        timeout=timeout_seconds,
    )

    response.raise_for_status()

    return response.text


def parse_dataset_year(dataset_code: str | None) -> int | None:

    if dataset_code is None:
        return None

    match = re.search(r"RP(\d{4})", dataset_code)

    if match:
        return int(match.group(1))

    return None


def parse_xml(
    xml_text: str,
    source_url: str,
) -> pd.DataFrame:

    root = ET.fromstring(xml_text)

    dataset = root.find(".//JeuDonnees")

    dataset_code = (
        dataset.attrib.get("code")
        if dataset is not None
        else None
    )

    dataset_year = parse_dataset_year(dataset_code)

    dataset_label = (
        dataset.findtext("Libelle")
        if dataset is not None
        else None
    )

    variable_labels = {
        variable.attrib.get("code"): variable.findtext("Libelle")
        for variable in root.findall(".//Variable")
    }

    modality_labels = {
        (
            variable.attrib.get("code"),
            modality.attrib.get("code"),
        ): modality.findtext("Libelle")
        for variable in root.findall(".//Variable")
        for modality in variable.findall("Modalite")
    }

    rows = []

    for cell in root.findall(".//Cellule"):

        zone = cell.find("Zone")
        measure = cell.find("Mesure")

        modalities = []

        for modality in cell.findall("Modalite"):

            modalities.append(
                {
                    "variable_code": modality.attrib.get(
                        "variable"
                    ),
                    "variable_label": variable_labels.get(
                        modality.attrib.get("variable")
                    ),
                    "modality_code": modality.attrib.get(
                        "code"
                    ),
                    "modality_label": modality_labels.get(
                        (
                            modality.attrib.get("variable"),
                            modality.attrib.get("code"),
                        )
                    ),
                }
            )

        rows.append(
            {
                "dataset_code": dataset_code,
                "year": dataset_year,
                "dataset_label": dataset_label,
                "source_url": source_url,
                "geo_level": (
                    zone.attrib.get("nivgeo")
                    if zone is not None
                    else None
                ),
                "departement_code": (
                    zone.attrib.get("codgeo")
                    if zone is not None
                    else None
                ),
                "measure_code": (
                    measure.attrib.get("code")
                    if measure is not None
                    else None
                ),
                "measure_label": (
                    measure.text
                    if measure is not None
                    else None
                ),
                "value": pd.to_numeric(
                    cell.findtext("Valeur"),
                    errors="coerce",
                ),
                "modalities_json": json.dumps(
                    modalities,
                    ensure_ascii=False,
                ),
            }
        )

    return pd.DataFrame(rows)


def fetch_one_department(
    dataset: str,
    departement_code: str,
) -> pd.DataFrame:

    url = build_url(
        dataset=dataset,
        departement_code=departement_code,
    )

    xml_text = fetch_xml(url)

    return parse_xml(
        xml_text=xml_text,
        source_url=url,
    )


def fetch_all_departements(
    dataset: str,
) -> pd.DataFrame:

    departements = get_departements()

    dfs = []

    total = len(departements)

    for i, dep in enumerate(departements, start=1):

        try:

            print(
                f"[{i}/{total}] "
                f"Département {dep}"
            )

            df = fetch_one_department(
                dataset=dataset,
                departement_code=dep,
            )

            dfs.append(df)

            time.sleep(0.2)

        except Exception as exc:

            print(
                f"Erreur département "
                f"{dep}: {exc}"
            )

    if not dfs:
        return pd.DataFrame()

    return pd.concat(
        dfs,
        ignore_index=True,
    )


def main():

    all_data = []

    for dataset in DATASETS:

        print()
        print("=" * 80)
        print(dataset)
        print("=" * 80)

        df = fetch_all_departements(dataset)

        all_data.append(df)

    final_df = pd.concat(
        all_data,
        ignore_index=True,
    )

    print()
    print(f"Nombre de lignes : {len(final_df):,}")

    final_df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8",
    )

    print()
    print("CSV sauvegardé :")
    print(OUTPUT_FILE)


if __name__ == "__main__":
    main()
