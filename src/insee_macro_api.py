"""Minimal client for INSEE Données locales API macro-economic extracts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from defusedxml import ElementTree as ET

import pandas as pd
import requests

BASE_URL = "https://api.insee.fr/donnees-locales/donnees"
DEFAULT_DATASET = "geo-SEXE-DIPL_19@GEO2023RP2020"
DEFAULT_MODALITIES = "all.all"
DEFAULT_RAW_OUTPUT = Path("data/raw/insee_macro/insee_donnees_locales_sample.xml")
DEFAULT_PARSED_OUTPUT = Path("data/processed/insee_macro/insee_macro_api_sample.csv")


def build_donnees_locales_url(
    dataset: str,
    geo_level: str,
    geo_code: str,
    modalities: str = DEFAULT_MODALITIES,
) -> str:
    geo_level = geo_level.upper()
    geo_code = geo_code.upper()
    return f"{BASE_URL}/{dataset}/{geo_level}-{geo_code}.{modalities}"


def fetch_xml(url: str, timeout_seconds: int = 30) -> str:
    response = requests.get(url, timeout=timeout_seconds)
    response.raise_for_status()
    return response.text


def parse_donnees_locales_xml(xml_text: str, source_url: str) -> pd.DataFrame:
    root = ET.fromstring(xml_text)
    dataset = root.find(".//JeuDonnees")
    dataset_code = dataset.attrib.get("code") if dataset is not None else None
    dataset_year = dataset.findtext("Annee") if dataset is not None else None
    dataset_label = dataset.findtext("Libelle") if dataset is not None else None
    dataset_source = dataset.findtext("Source") if dataset is not None else None

    variable_labels = {
        variable.attrib.get("code"): variable.findtext("Libelle")
        for variable in root.findall(".//Variable")
    }
    modality_labels = {
        (variable.attrib.get("code"), modality.attrib.get("code")): modality.findtext("Libelle")
        for variable in root.findall(".//Variable")
        for modality in variable.findall("Modalite")
    }

    rows = []
    for cell in root.findall(".//Cellule"):
        zone = cell.find("Zone")
        measure = cell.find("Mesure")
        modalities = [
            {
                "variable_code": modality.attrib.get("variable"),
                "variable_label": variable_labels.get(modality.attrib.get("variable")),
                "modality_code": modality.attrib.get("code"),
                "modality_label": modality_labels.get(
                    (modality.attrib.get("variable"), modality.attrib.get("code"))
                ),
            }
            for modality in cell.findall("Modalite")
        ]
        rows.append(
            {
                "api_source": "insee_donnees_locales",
                "source_url": source_url,
                "dataset_code": dataset_code,
                "dataset_year": dataset_year,
                "dataset_label": dataset_label,
                "dataset_source": dataset_source,
                "geo_level": zone.attrib.get("nivgeo") if zone is not None else None,
                "departement_code": zone.attrib.get("codgeo") if zone is not None else None,
                "measure_code": measure.attrib.get("code") if measure is not None else None,
                "measure_label": measure.text if measure is not None else None,
                "modalities_json": json.dumps(modalities, ensure_ascii=False),
                "value": pd.to_numeric(cell.findtext("Valeur"), errors="coerce"),
            }
        )

    return pd.DataFrame(rows)


def run_sample_fetch(
    dataset: str = DEFAULT_DATASET,
    geo_level: str = "DEP",
    geo_code: str = "75",
    modalities: str = DEFAULT_MODALITIES,
    raw_output: Path = DEFAULT_RAW_OUTPUT,
    parsed_output: Path = DEFAULT_PARSED_OUTPUT,
) -> pd.DataFrame:
    url = build_donnees_locales_url(
        dataset=dataset,
        geo_level=geo_level,
        geo_code=geo_code,
        modalities=modalities,
    )
    xml_text = fetch_xml(url)
    raw_output.parent.mkdir(parents=True, exist_ok=True)
    parsed_output.parent.mkdir(parents=True, exist_ok=True)
    raw_output.write_text(xml_text, encoding="utf-8")

    parsed = parse_donnees_locales_xml(xml_text, source_url=url)
    parsed.to_csv(parsed_output, index=False)
    return parsed


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch a sample from INSEE Données locales API.")
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--geo-level", default="DEP")
    parser.add_argument("--geo-code", default="75")
    parser.add_argument("--modalities", default=DEFAULT_MODALITIES)
    parser.add_argument("--raw-output", default=str(DEFAULT_RAW_OUTPUT))
    parser.add_argument("--parsed-output", default=str(DEFAULT_PARSED_OUTPUT))
    return parser


def main() -> None:
    args = _build_arg_parser().parse_args()
    parsed = run_sample_fetch(
        dataset=args.dataset,
        geo_level=args.geo_level,
        geo_code=args.geo_code,
        modalities=args.modalities,
        raw_output=Path(args.raw_output),
        parsed_output=Path(args.parsed_output),
    )
    print(
        "INSEE Données locales sample fetched | "
        f"rows={len(parsed)} "
        f"departements={parsed['departement_code'].nunique() if not parsed.empty else 0}"
    )


if __name__ == "__main__":
    main()
