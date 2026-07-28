"""Build a coherent analytical SQLite database from curated BDF and INSEE data."""

from __future__ import annotations

import argparse
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.statinfo_bi_quality import EXPECTED_DEPARTMENT_CODES

DEFAULT_BDF_CURATED = Path("data/processed/statinfo_departements_bi_curated.csv")
DEFAULT_INSEE_MACRO = Path("data/processed/insee_macro/gold/2026/insee_macro_departements_long.csv")
DEFAULT_SURENDETTEMENT = Path("data/processed/surendettement/gold/surendettement_departements.csv")
DEFAULT_INSEE_METADATA = Path("data/raw/insee_macro/dossier_complet/2026/extracted/meta_dossier_complet.csv")
DEFAULT_OUTPUT_DB = Path("data/processed/analytics/surendettement_macro_analytics.db")
DATABASE_VERSION = "surendettement_macro_analytics_v3"

SELECTED_INSEE_INDICATORS = {
    "P22_POP": ("Population", "démographie"),
    "P22_POP0014": ("Population de 0 à 14 ans", "démographie"),
    "P22_POP1529": ("Population de 15 à 29 ans", "démographie"),
    "P22_POP3044": ("Population de 30 à 44 ans", "démographie"),
    "P22_POP4559": ("Population de 45 à 59 ans", "démographie"),
    "P22_POP6074": ("Population de 60 à 74 ans", "démographie"),
    "P22_POP7589": ("Population de 75 à 89 ans", "démographie"),
    "P22_POP90P": ("Population de 90 ans ou plus", "démographie"),
    "P22_POP1564": ("Population de 15 à 64 ans", "démographie"),
    "P22_ACT1564": ("Personnes actives de 15 à 64 ans", "emploi_chômage"),
    "P22_ACTOCC1564": ("Personnes actives occupées de 15 à 64 ans", "emploi_chômage"),
    "P22_CHOM1564": ("Chômeurs de 15 à 64 ans", "emploi_chômage"),
    "P22_EMPLT": ("Emplois au lieu de travail", "emploi_chômage"),
    "P22_LOG": ("Logements", "logement"),
    "P22_RP": ("Résidences principales", "logement"),
    "P22_RSECOCC": ("Résidences secondaires et logements occasionnels", "logement"),
    "P22_LOGVAC": ("Logements vacants", "logement"),
    "P22_RP_PROP": ("Résidences principales occupées par des propriétaires", "logement"),
    "P22_RP_LOC": ("Résidences principales occupées par des locataires", "logement"),
    "C22_MEN": ("Ménages", "familles"),
    "C22_MENPSEUL": ("Ménages d’une personne", "familles"),
    "C22_FAM": ("Familles", "familles"),
    "C22_FAMMONO": ("Familles monoparentales", "familles"),
    "P22_NSCOL15P": ("Personnes non scolarisées de 15 ans ou plus", "formation"),
    "P22_NSCOL15P_DIPLMIN": ("Personnes sans diplôme ou titulaires au plus du CEP", "formation"),
    "P22_NSCOL15P_SUP5": ("Diplômés de l’enseignement supérieur Bac +5 ou plus", "formation"),
}
VALID_SURENDETTEMENT_INDICATORS = {"surendettement_dossiers_deposes"}

REGION_DEPARTMENTS = {
    "Auvergne-Rhône-Alpes": {"01", "03", "07", "15", "26", "38", "42", "43", "63", "69", "73", "74"},
    "Bourgogne-Franche-Comté": {"21", "25", "39", "58", "70", "71", "89", "90"},
    "Bretagne": {"22", "29", "35", "56"},
    "Centre-Val de Loire": {"18", "28", "36", "37", "41", "45"},
    "Corse": {"2A", "2B"},
    "Grand Est": {"08", "10", "51", "52", "54", "55", "57", "67", "68", "88"},
    "Hauts-de-France": {"02", "59", "60", "62", "80"},
    "Île-de-France": {"75", "77", "78", "91", "92", "93", "94", "95"},
    "Normandie": {"14", "27", "50", "61", "76"},
    "Nouvelle-Aquitaine": {"16", "17", "19", "23", "24", "33", "40", "47", "64", "79", "86", "87"},
    "Occitanie": {"09", "11", "12", "30", "31", "32", "34", "46", "48", "65", "66", "81", "82"},
    "Pays de la Loire": {"44", "49", "53", "72", "85"},
    "Provence-Alpes-Côte d’Azur": {"04", "05", "06", "13", "83", "84"},
}
DEPARTMENT_TO_REGION = {
    department: region
    for region, departments in REGION_DEPARTMENTS.items()
    for department in departments
}


def build_analytics_database(
    bdf_curated_path: Path = DEFAULT_BDF_CURATED,
    insee_macro_path: Path = DEFAULT_INSEE_MACRO,
    surendettement_path: Path = DEFAULT_SURENDETTEMENT,
    insee_metadata_path: Path = DEFAULT_INSEE_METADATA,
    output_db: Path = DEFAULT_OUTPUT_DB,
) -> dict[str, int]:
    output_db.parent.mkdir(parents=True, exist_ok=True)
    bdf = _load_bdf_curated(bdf_curated_path)
    insee = _load_insee_macro(insee_macro_path, metadata_path=insee_metadata_path)
    surendettement = _load_surendettement(surendettement_path)
    departments = _build_departments_dimension(bdf=bdf, insee=insee, surendettement=surendettement)
    indicators = _build_indicator_dimension(bdf=bdf, insee=insee, surendettement=surendettement)

    with sqlite3.connect(output_db) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        _drop_existing_objects(connection)
        _create_schema(connection)
        _write_frame(connection, "dim_department", departments)
        _write_frame(connection, "dim_indicator", indicators)
        _write_frame(connection, "fact_surendettement", _build_surendettement_fact(surendettement))
        _write_frame(connection, "fact_bdf_statinfo", _build_bdf_fact(bdf))
        _write_frame(connection, "fact_insee_macro", _build_insee_fact(insee))
        _write_frame(
            connection,
            "pipeline_metadata",
            _build_metadata(bdf_curated_path, insee_macro_path, surendettement_path, insee_metadata_path),
        )
        _create_indexes(connection)
        _create_views(connection)
        connection.commit()

        return {
            "departments": _count_rows(connection, "dim_department"),
            "indicators": _count_rows(connection, "dim_indicator"),
            "surendettement_rows": _count_rows(connection, "fact_surendettement"),
            "bdf_rows": _count_rows(connection, "fact_bdf_statinfo"),
            "insee_rows": _count_rows(connection, "fact_insee_macro"),
        }


def _load_bdf_curated(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"departement_code": str})
    required = {
        "reference_period",
        "reference_year",
        "reference_month_number",
        "region",
        "departement_code",
        "departement_name",
        "indicator_code",
        "indicator_name",
        "indicator_group",
        "unit",
        "value",
        "source_file",
    }
    _check_required_columns(df, required, path)
    df["departement_code"] = df["departement_code"].map(_standardize_department_code)
    return df


def _load_insee_macro(path: Path, metadata_path: Path = DEFAULT_INSEE_METADATA) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"departement_code": str})
    required = {
        "reference_year",
        "departement_code",
        "indicator_code",
        "indicator_name",
        "indicator_group",
        "aggregation_rule",
        "value",
        "source_dataset",
    }
    _check_required_columns(df, required, path)
    df["departement_code"] = df["departement_code"].map(_standardize_department_code)
    if metadata_path.exists():
        metadata = _load_insee_metadata(metadata_path)
        df = df.merge(metadata, on="indicator_code", how="left")
        df["indicator_name"] = df["metadata_indicator_name"].combine_first(df["indicator_name"])
        df["indicator_group"] = df["metadata_indicator_group"].combine_first(df["indicator_group"])
        df = df.drop(columns=["metadata_indicator_name", "metadata_indicator_group"])
    df = df[df["indicator_code"].isin(SELECTED_INSEE_INDICATORS)].copy()
    df["reference_year"] = df.apply(_insee_indicator_year, axis=1)
    df["indicator_name"] = df["indicator_code"].map(
        {code: metadata[0] for code, metadata in SELECTED_INSEE_INDICATORS.items()}
    )
    df["indicator_group"] = df["indicator_code"].map(
        {code: metadata[1] for code, metadata in SELECTED_INSEE_INDICATORS.items()}
    )
    df["aggregation_rule"] = "sum"
    return df


def _load_surendettement(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(
            columns=["reference_year", "departement_code", "indicator_code", "indicator_name", "value", "source_file"]
        )
    df = pd.read_csv(path, dtype={"departement_code": str})
    if {"reference_year", "departement_code", "indicator_code", "indicator_name", "value", "source_file"}.issubset(
        df.columns
    ):
        df["reference_year"] = pd.to_numeric(df["reference_year"], errors="coerce").astype("Int64")
        df["departement_code"] = df["departement_code"].map(_standardize_department_code)
    else:
        required = {"year", "departement", "indicator_name", "value", "source_file"}
        _check_required_columns(df, required, path)
        df["reference_year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
        df["departement_code"] = df["departement"].map(_standardize_department_code)
        df["indicator_name"] = df["indicator_name"].astype(str)
        df["indicator_code"] = "surendettement_" + df["indicator_name"].map(_slugify)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["reference_year", "departement_code", "value"]).copy()
    return df[
        df["departement_code"].isin(EXPECTED_DEPARTMENT_CODES)
        & df["indicator_code"].isin(VALID_SURENDETTEMENT_INDICATORS)
    ].copy()


def _insee_indicator_year(row: pd.Series) -> int:
    label = str(row.get("indicator_name") or "")
    label_match = re.search(r"\b(20\d{2})\b", label)
    if label_match:
        return int(label_match.group(1))
    code_match = re.search(r"(?:^|_)(?:P|C)?(\d{2})(?:_|[A-Z])", str(row["indicator_code"]), re.I)
    if code_match:
        return 2000 + int(code_match.group(1))
    raise ValueError(f"Cannot infer INSEE reference year for {row['indicator_code']}")


def _load_insee_metadata(path: Path) -> pd.DataFrame:
    metadata = pd.read_csv(path, sep=";", dtype=str)
    required = {"COD_VAR", "LIB_VAR", "LIB_VAR_LONG", "THEME"}
    _check_required_columns(metadata, required, path)
    metadata = metadata.drop_duplicates("COD_VAR").copy()
    metadata["metadata_indicator_name"] = metadata["LIB_VAR_LONG"].fillna(metadata["LIB_VAR"])
    metadata["metadata_indicator_group"] = metadata["THEME"]
    return metadata.rename(columns={"COD_VAR": "indicator_code"})[
        ["indicator_code", "metadata_indicator_name", "metadata_indicator_group"]
    ]


def _build_departments_dimension(bdf: pd.DataFrame, insee: pd.DataFrame, surendettement: pd.DataFrame) -> pd.DataFrame:
    bdf_deps = (
        bdf[["departement_code", "departement_name", "region"]]
        .dropna(subset=["departement_code"])
        .drop_duplicates("departement_code")
        .rename(columns={"region": "region_name"})
    )
    insee_deps = (
        insee[["departement_code", "departement_name"]]
        .dropna(subset=["departement_code"])
        .drop_duplicates("departement_code")
    )
    sur_deps = surendettement[["departement_code"]].dropna().drop_duplicates()
    departments = insee_deps.merge(bdf_deps, on="departement_code", how="outer", suffixes=("_insee", "_bdf"))
    departments = departments.merge(sur_deps, on="departement_code", how="outer")
    departments["departement_name"] = departments["departement_name_bdf"].combine_first(
        departments["departement_name_insee"]
    )
    departments["region_name"] = departments["departement_code"].map(DEPARTMENT_TO_REGION)
    departments["is_metropolitan_scope"] = True
    return departments[
        ["departement_code", "departement_name", "region_name", "is_metropolitan_scope"]
    ].sort_values("departement_code")


def _build_indicator_dimension(bdf: pd.DataFrame, insee: pd.DataFrame, surendettement: pd.DataFrame) -> pd.DataFrame:
    bdf_indicators = (
        bdf[["indicator_code", "indicator_name", "indicator_group", "unit"]]
        .drop_duplicates("indicator_code")
        .assign(source_system="bdf_statinfo", aggregation_rule=pd.NA)
    )
    insee_indicators = (
        insee[["indicator_code", "indicator_name", "indicator_group", "aggregation_rule"]]
        .drop_duplicates("indicator_code")
        .assign(source_system="insee_macro", unit=pd.NA)
    )
    sur_indicators = (
        surendettement[["indicator_code", "indicator_name"]]
        .drop_duplicates("indicator_code")
        .assign(source_system="surendettement", indicator_group="surendettement", unit=pd.NA, aggregation_rule="sum")
    )
    indicators = pd.concat([bdf_indicators, insee_indicators, sur_indicators], ignore_index=True)
    indicators["indicator_key"] = indicators["source_system"] + ":" + indicators["indicator_code"].astype(str)
    return indicators[
        [
            "indicator_key",
            "source_system",
            "indicator_code",
            "indicator_name",
            "indicator_group",
            "unit",
            "aggregation_rule",
        ]
    ].sort_values(["source_system", "indicator_code"])


def _build_surendettement_fact(surendettement: pd.DataFrame) -> pd.DataFrame:
    fact = surendettement.copy()
    if fact.empty:
        return pd.DataFrame(
            columns=["reference_year", "departement_code", "indicator_key", "value", "source_file"]
        )
    fact["indicator_key"] = "surendettement:" + fact["indicator_code"].astype(str)
    return fact[["reference_year", "departement_code", "indicator_key", "value", "source_file"]]


def _build_bdf_fact(bdf: pd.DataFrame) -> pd.DataFrame:
    fact = bdf.copy()
    fact["indicator_key"] = "bdf_statinfo:" + fact["indicator_code"].astype(str)
    fact["value"] = pd.to_numeric(fact["value"], errors="coerce")
    return fact[
        [
            "reference_period",
            "reference_year",
            "reference_month_number",
            "departement_code",
            "indicator_key",
            "value",
            "source_file",
            "pipeline_version",
        ]
    ]


def _build_insee_fact(insee: pd.DataFrame) -> pd.DataFrame:
    fact = insee.copy()
    fact["indicator_key"] = "insee_macro:" + fact["indicator_code"].astype(str)
    fact["value"] = pd.to_numeric(fact["value"], errors="coerce")
    return fact[
        [
            "reference_year",
            "departement_code",
            "indicator_key",
            "value",
            "source_dataset",
            "pipeline_version",
        ]
    ]


def _build_metadata(
    bdf_path: Path,
    insee_path: Path,
    surendettement_path: Path,
    insee_metadata_path: Path,
) -> pd.DataFrame:
    built_at = datetime.now(timezone.utc).isoformat()
    return pd.DataFrame(
        [
            {
                "database_version": DATABASE_VERSION,
                "source_system": "bdf_statinfo",
                "source_path": str(bdf_path),
                "built_at": built_at,
            },
            {
                "database_version": DATABASE_VERSION,
                "source_system": "insee_macro",
                "source_path": str(insee_path),
                "built_at": built_at,
            },
            {
                "database_version": DATABASE_VERSION,
                "source_system": "surendettement",
                "source_path": str(surendettement_path),
                "built_at": built_at,
            },
            {
                "database_version": DATABASE_VERSION,
                "source_system": "insee_metadata",
                "source_path": str(insee_metadata_path),
                "built_at": built_at,
            },
        ]
    )


def _drop_existing_objects(connection: sqlite3.Connection) -> None:
    views = [
        "v_bdf_total_deposits",
        "v_bdf_total_deposits_with_insee_macro",
        "v_surendettement_annual",
        "v_surendettement_with_insee_macro",
        "v_insee_macro_region",
        "v_insee_macro_region_selected",
    ]
    tables = [
        "pipeline_metadata",
        "fact_insee_macro",
        "fact_bdf_statinfo",
        "fact_surendettement",
        "dim_indicator",
        "dim_department",
    ]
    for name in views:
        connection.execute(f"DROP VIEW IF EXISTS {name}")
    for name in tables:
        connection.execute(f"DROP TABLE IF EXISTS {name}")


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE dim_department (
            departement_code TEXT PRIMARY KEY,
            departement_name TEXT,
            region_name TEXT,
            is_metropolitan_scope INTEGER NOT NULL
        );

        CREATE TABLE dim_indicator (
            indicator_key TEXT PRIMARY KEY,
            source_system TEXT NOT NULL,
            indicator_code TEXT NOT NULL,
            indicator_name TEXT,
            indicator_group TEXT,
            unit TEXT,
            aggregation_rule TEXT
        );

        CREATE TABLE fact_bdf_statinfo (
            reference_period TEXT NOT NULL,
            reference_year INTEGER NOT NULL,
            reference_month_number INTEGER NOT NULL,
            departement_code TEXT NOT NULL,
            indicator_key TEXT NOT NULL,
            value REAL NOT NULL,
            source_file TEXT,
            pipeline_version TEXT,
            FOREIGN KEY (departement_code) REFERENCES dim_department(departement_code),
            FOREIGN KEY (indicator_key) REFERENCES dim_indicator(indicator_key)
        );

        CREATE TABLE fact_surendettement (
            reference_year INTEGER NOT NULL,
            departement_code TEXT NOT NULL,
            indicator_key TEXT NOT NULL,
            value REAL NOT NULL,
            source_file TEXT,
            FOREIGN KEY (departement_code) REFERENCES dim_department(departement_code),
            FOREIGN KEY (indicator_key) REFERENCES dim_indicator(indicator_key)
        );

        CREATE TABLE fact_insee_macro (
            reference_year INTEGER NOT NULL,
            departement_code TEXT NOT NULL,
            indicator_key TEXT NOT NULL,
            value REAL NOT NULL,
            source_dataset TEXT,
            pipeline_version TEXT,
            FOREIGN KEY (departement_code) REFERENCES dim_department(departement_code),
            FOREIGN KEY (indicator_key) REFERENCES dim_indicator(indicator_key)
        );

        CREATE TABLE pipeline_metadata (
            database_version TEXT NOT NULL,
            source_system TEXT NOT NULL,
            source_path TEXT NOT NULL,
            built_at TEXT NOT NULL
        );
        """
    )


def _create_indexes(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE INDEX idx_bdf_department_period ON fact_bdf_statinfo(departement_code, reference_period);
        CREATE INDEX idx_bdf_indicator ON fact_bdf_statinfo(indicator_key);
        CREATE INDEX idx_surendettement_department_year ON fact_surendettement(departement_code, reference_year);
        CREATE INDEX idx_surendettement_indicator ON fact_surendettement(indicator_key);
        CREATE INDEX idx_insee_department_year ON fact_insee_macro(departement_code, reference_year);
        CREATE INDEX idx_insee_indicator ON fact_insee_macro(indicator_key);
        CREATE UNIQUE INDEX uq_bdf_fact
            ON fact_bdf_statinfo(reference_period, departement_code, indicator_key);
        CREATE UNIQUE INDEX uq_insee_fact
            ON fact_insee_macro(reference_year, departement_code, indicator_key);
        """
    )


def _create_views(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE VIEW v_bdf_total_deposits AS
        SELECT
            b.reference_period,
            b.reference_year,
            b.reference_month_number,
            b.departement_code,
            d.departement_name,
            d.region_name,
            b.value AS bdf_total_deposits_value
        FROM fact_bdf_statinfo b
        JOIN dim_indicator i ON i.indicator_key = b.indicator_key
        LEFT JOIN dim_department d ON d.departement_code = b.departement_code
        WHERE i.source_system = 'bdf_statinfo'
          AND i.indicator_code = 'total';

        CREATE VIEW v_surendettement_annual AS
        SELECT
            s.reference_year,
            s.departement_code,
            d.departement_name,
            d.region_name,
            SUM(s.value) AS surendettement_value
        FROM fact_surendettement s
        LEFT JOIN dim_department d ON d.departement_code = s.departement_code
        GROUP BY s.reference_year, s.departement_code, d.departement_name, d.region_name;

        CREATE VIEW v_bdf_total_deposits_with_insee_macro AS
        SELECT
            b.reference_period AS bdf_reference_period,
            b.reference_year AS bdf_reference_year,
            b.reference_month_number AS bdf_reference_month_number,
            b.departement_code,
            b.departement_name,
            b.region_name,
            b.bdf_total_deposits_value,
            m.reference_year AS macro_reference_year,
            i.indicator_code AS macro_indicator_code,
            i.indicator_name AS macro_indicator_name,
            i.indicator_group AS macro_indicator_group,
            m.value AS macro_value
        FROM v_bdf_total_deposits b
        JOIN fact_insee_macro m
          ON m.departement_code = b.departement_code
         AND m.reference_year = (
             SELECT MAX(reference_year)
             FROM fact_insee_macro
             WHERE reference_year <= b.reference_year + 1
         )
        JOIN dim_indicator i ON i.indicator_key = m.indicator_key
        WHERE i.source_system = 'insee_macro';

        CREATE VIEW v_surendettement_with_insee_macro AS
        SELECT
            s.reference_year,
            s.departement_code,
            s.departement_name,
            s.region_name,
            s.surendettement_value,
            m.reference_year AS macro_reference_year,
            i.indicator_code AS macro_indicator_code,
            i.indicator_name AS macro_indicator_name,
            i.indicator_group AS macro_indicator_group,
            m.value AS macro_value
        FROM v_surendettement_annual s
        JOIN fact_insee_macro m
          ON m.departement_code = s.departement_code
         AND m.reference_year = (
             SELECT MAX(reference_year)
             FROM fact_insee_macro
             WHERE reference_year <= s.reference_year + 1
         )
        JOIN dim_indicator i ON i.indicator_key = m.indicator_key
        WHERE i.source_system = 'insee_macro';

        CREATE VIEW v_insee_macro_region AS
        SELECT
            m.reference_year,
            d.region_name,
            i.indicator_code,
            i.indicator_name,
            i.indicator_group,
            i.aggregation_rule,
            SUM(m.value) AS value
        FROM fact_insee_macro m
        JOIN dim_department d ON d.departement_code = m.departement_code
        JOIN dim_indicator i ON i.indicator_key = m.indicator_key
        WHERE i.source_system = 'insee_macro'
          AND d.region_name IS NOT NULL
        GROUP BY
            m.reference_year, d.region_name, i.indicator_code,
            i.indicator_name, i.indicator_group, i.aggregation_rule;

        CREATE VIEW v_insee_macro_region_selected AS
        WITH ratio_definitions(
            indicator_code, indicator_name, indicator_group,
            numerator_code, denominator_code
        ) AS (
            VALUES
                ('part_population_0014', 'Part de la population de 0 à 14 ans', 'démographie', 'P22_POP0014', 'P22_POP'),
                ('part_population_1529', 'Part de la population de 15 à 29 ans', 'démographie', 'P22_POP1529', 'P22_POP'),
                ('part_population_3044', 'Part de la population de 30 à 44 ans', 'démographie', 'P22_POP3044', 'P22_POP'),
                ('part_population_4559', 'Part de la population de 45 à 59 ans', 'démographie', 'P22_POP4559', 'P22_POP'),
                ('part_population_6074', 'Part de la population de 60 à 74 ans', 'démographie', 'P22_POP6074', 'P22_POP'),
                ('part_population_7589', 'Part de la population de 75 à 89 ans', 'démographie', 'P22_POP7589', 'P22_POP'),
                ('part_population_90p', 'Part de la population de 90 ans ou plus', 'démographie', 'P22_POP90P', 'P22_POP'),
                ('taux_activite_1564', 'Taux d’activité des 15 à 64 ans', 'emploi_chômage', 'P22_ACT1564', 'P22_POP1564'),
                ('taux_emploi_1564', 'Taux d’emploi des 15 à 64 ans', 'emploi_chômage', 'P22_ACTOCC1564', 'P22_POP1564'),
                ('taux_chomage_1564', 'Taux de chômage des 15 à 64 ans', 'emploi_chômage', 'P22_CHOM1564', 'P22_ACT1564'),
                ('part_residences_principales', 'Part des résidences principales', 'logement', 'P22_RP', 'P22_LOG'),
                ('part_residences_secondaires', 'Part des résidences secondaires', 'logement', 'P22_RSECOCC', 'P22_LOG'),
                ('part_logements_vacants', 'Part des logements vacants', 'logement', 'P22_LOGVAC', 'P22_LOG'),
                ('part_proprietaires', 'Part des résidences principales occupées par des propriétaires', 'logement', 'P22_RP_PROP', 'P22_RP'),
                ('part_locataires', 'Part des résidences principales occupées par des locataires', 'logement', 'P22_RP_LOC', 'P22_RP'),
                ('part_menages_seuls', 'Part des ménages d’une personne', 'familles', 'C22_MENPSEUL', 'C22_MEN'),
                ('part_familles_monoparentales', 'Part des familles monoparentales', 'familles', 'C22_FAMMONO', 'C22_FAM'),
                ('part_sans_diplome', 'Part des personnes sans diplôme ou titulaires au plus du CEP', 'formation', 'P22_NSCOL15P_DIPLMIN', 'P22_NSCOL15P'),
                ('part_diplomees_bac5', 'Part des diplômés Bac +5 ou plus', 'formation', 'P22_NSCOL15P_SUP5', 'P22_NSCOL15P')
        ),
        derived AS (
            SELECT
                numerator.reference_year,
                numerator.region_name,
                definitions.indicator_code,
                definitions.indicator_name,
                definitions.indicator_group,
                'derived_ratio' AS aggregation_rule,
                100.0 * numerator.value / NULLIF(denominator.value, 0) AS value
            FROM ratio_definitions definitions
            JOIN v_insee_macro_region numerator
              ON numerator.indicator_code = definitions.numerator_code
            JOIN v_insee_macro_region denominator
              ON denominator.reference_year = numerator.reference_year
             AND denominator.region_name = numerator.region_name
             AND denominator.indicator_code = definitions.denominator_code
        )
        SELECT
            reference_year, region_name, indicator_code, indicator_name,
            indicator_group, aggregation_rule, value
        FROM v_insee_macro_region
        UNION ALL
        SELECT
            reference_year, region_name, indicator_code, indicator_name,
            indicator_group, aggregation_rule, value
        FROM derived;
        """
    )


def _write_frame(connection: sqlite3.Connection, table_name: str, frame: pd.DataFrame) -> None:
    frame.to_sql(table_name, connection, if_exists="append", index=False)


def _count_rows(connection: sqlite3.Connection, table_name: str) -> int:
    return int(connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


def _check_required_columns(df: pd.DataFrame, columns: set[str], path: Path) -> None:
    missing = sorted(columns - set(df.columns))
    if missing:
        raise ValueError(f"Missing columns in {path}: {', '.join(missing)}")


def _standardize_department_code(value: object) -> str:
    text = str(value).strip().upper().replace(".0", "").replace(".", "")
    return text.zfill(2) if text.isdigit() else text


def _slugify(value: object) -> str:
    text = str(value).strip().lower()
    text = "".join(char if char.isalnum() else "_" for char in text)
    text = "_".join(part for part in text.split("_") if part)
    return text or "unknown"


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the analytical SQLite database.")
    parser.add_argument("--bdf-curated", default=str(DEFAULT_BDF_CURATED))
    parser.add_argument("--insee-macro", default=str(DEFAULT_INSEE_MACRO))
    parser.add_argument("--surendettement", default=str(DEFAULT_SURENDETTEMENT))
    parser.add_argument("--insee-metadata", default=str(DEFAULT_INSEE_METADATA))
    parser.add_argument("--output-db", default=str(DEFAULT_OUTPUT_DB))
    return parser


def main() -> None:
    args = _build_arg_parser().parse_args()
    summary = build_analytics_database(
        bdf_curated_path=Path(args.bdf_curated),
        insee_macro_path=Path(args.insee_macro),
        surendettement_path=Path(args.surendettement),
        insee_metadata_path=Path(args.insee_metadata),
        output_db=Path(args.output_db),
    )
    print(
        "Analytics database built | "
        f"departments={summary['departments']} "
        f"indicators={summary['indicators']} "
        f"surendettement_rows={summary['surendettement_rows']} "
        f"bdf_rows={summary['bdf_rows']} "
        f"insee_rows={summary['insee_rows']}"
    )


if __name__ == "__main__":
    main()
