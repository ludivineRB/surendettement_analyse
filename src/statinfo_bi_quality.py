"""Quality checks, curated export, and business analysis for STAT INFO BI data."""

from __future__ import annotations

import argparse
import re
import unicodedata
from pathlib import Path
from typing import Iterable

import pandas as pd

from src.statinfo_bi_pipeline import DEPOSITS_REGION_INDICATORS

PIPELINE_VERSION = "statinfo_bi_curated_v1"

DEFAULT_INPUT_CSV = Path("data/processed/statinfo_departements_bi_candidate.csv")
DEFAULT_CURATED_CSV = Path("data/processed/statinfo_departements_bi_curated.csv")
DEFAULT_INDICATOR_DICTIONARY_CSV = Path("data/processed/statinfo_bi_indicator_dictionary.csv")
DEFAULT_VALIDATION_REPORT = Path("data/processed/statinfo_bi_validation_report.md")
DEFAULT_BUSINESS_REPORT = Path("data/processed/statinfo_bi_business_analysis.md")

MONTHS = {
    "janvier": 1,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
}
MONTH_LABELS = {
    1: "janvier",
    2: "février",
    3: "mars",
    4: "avril",
    5: "mai",
    6: "juin",
    7: "juillet",
    8: "août",
    9: "septembre",
    10: "octobre",
    11: "novembre",
    12: "décembre",
}
EXPECTED_DEPARTMENT_CODES = [
    "01",
    "02",
    "03",
    "04",
    "05",
    "06",
    "07",
    "08",
    "09",
    "10",
    "11",
    "12",
    "13",
    "14",
    "15",
    "16",
    "17",
    "18",
    "19",
    "21",
    "22",
    "23",
    "24",
    "25",
    "26",
    "27",
    "28",
    "29",
    "30",
    "31",
    "32",
    "33",
    "34",
    "35",
    "36",
    "37",
    "38",
    "39",
    "40",
    "41",
    "42",
    "43",
    "44",
    "45",
    "46",
    "47",
    "48",
    "49",
    "50",
    "51",
    "52",
    "53",
    "54",
    "55",
    "56",
    "57",
    "58",
    "59",
    "60",
    "61",
    "62",
    "63",
    "64",
    "65",
    "66",
    "67",
    "68",
    "69",
    "70",
    "71",
    "72",
    "73",
    "74",
    "75",
    "76",
    "77",
    "78",
    "79",
    "80",
    "81",
    "82",
    "83",
    "84",
    "85",
    "86",
    "87",
    "88",
    "89",
    "90",
    "91",
    "92",
    "93",
    "94",
    "95",
    "2A",
    "2B",
]
INDICATOR_METADATA = [
    {
        "indicator_code": "comptes_ordinaires_crediteurs",
        "indicator_name": "Comptes ordinaires créditeurs",
        "indicator_group": "dépôts à vue",
        "unit": "milliards_euros",
        "indicator_order": 1,
    },
    {
        "indicator_code": "autres_livrets",
        "indicator_name": "Autres livrets (1)",
        "indicator_group": "épargne réglementée et livrets",
        "unit": "milliards_euros",
        "indicator_order": 2,
    },
    {
        "indicator_code": "livrets_epargne_populaire",
        "indicator_name": "Livrets d'épargne populaire",
        "indicator_group": "épargne réglementée et livrets",
        "unit": "milliards_euros",
        "indicator_order": 3,
    },
    {
        "indicator_code": "livrets_developpement_durable",
        "indicator_name": "Livrets de développement durable",
        "indicator_group": "épargne réglementée et livrets",
        "unit": "milliards_euros",
        "indicator_order": 4,
    },
    {
        "indicator_code": "cel",
        "indicator_name": "C.E.L",
        "indicator_group": "épargne logement",
        "unit": "milliards_euros",
        "indicator_order": 5,
    },
    {
        "indicator_code": "comptes_especes_pea_per_divers",
        "indicator_name": "Comptes espèces PEA, PER divers",
        "indicator_group": "placements divers",
        "unit": "milliards_euros",
        "indicator_order": 6,
    },
    {
        "indicator_code": "plans_epargne_populaire",
        "indicator_name": "Plans d'épargne populaire",
        "indicator_group": "épargne réglementée et livrets",
        "unit": "milliards_euros",
        "indicator_order": 7,
    },
    {
        "indicator_code": "comptes_crediteurs_a_terme",
        "indicator_name": "Comptes créditeurs à terme",
        "indicator_group": "dépôts à terme",
        "unit": "milliards_euros",
        "indicator_order": 8,
    },
    {
        "indicator_code": "pel",
        "indicator_name": "P.E.L",
        "indicator_group": "épargne logement",
        "unit": "milliards_euros",
        "indicator_order": 9,
    },
    {
        "indicator_code": "bons_caisse_epargne",
        "indicator_name": "Bons de caisse et d'épargne (2)",
        "indicator_group": "autres dépôts",
        "unit": "milliards_euros",
        "indicator_order": 10,
    },
    {
        "indicator_code": "total",
        "indicator_name": "TOTAL",
        "indicator_group": "total",
        "unit": "milliards_euros",
        "indicator_order": 11,
    },
]


def build_indicator_dictionary() -> pd.DataFrame:
    return pd.DataFrame(INDICATOR_METADATA)


def curate_bi_frame(df: pd.DataFrame) -> pd.DataFrame:
    curated = df.copy()
    curated["departement_code"] = curated["departement_code"].map(_standardize_department_code)
    curated["reference_month_normalized"] = curated["reference_month"].map(_normalize_month_text)
    curated["reference_month_number"] = curated["reference_month_normalized"].map(MONTHS).astype("Int64")
    curated["reference_month_label"] = curated["reference_month_number"].map(MONTH_LABELS)
    curated["reference_year"] = pd.to_numeric(curated["reference_year"], errors="coerce").astype("Int64")
    curated["value"] = pd.to_numeric(curated["value"], errors="coerce")
    curated["indicator_name"] = curated["indicator_name"].map(_standardize_indicator_name)

    indicator_dictionary = build_indicator_dictionary()
    curated = curated.merge(indicator_dictionary, on="indicator_name", how="left")
    curated["reference_period"] = (
        curated["reference_year"].astype("string")
        + "-"
        + curated["reference_month_number"].astype("string").str.zfill(2)
    )
    curated["pipeline_version"] = PIPELINE_VERSION

    columns = [
        "reference_period",
        "reference_year",
        "reference_month_number",
        "reference_month_label",
        "region",
        "departement_code",
        "departement_name",
        "indicator_code",
        "indicator_name",
        "indicator_group",
        "indicator_order",
        "unit",
        "value",
        "source_file",
        "page_number",
        "pipeline_version",
    ]
    return curated.sort_values(
        ["reference_period", "region", "departement_code", "indicator_order"],
        na_position="last",
    ).reset_index(drop=True)[columns]


def build_validation_summary(curated: pd.DataFrame) -> dict:
    extracted_departments = set(curated["departement_code"].dropna().unique())
    expected_departments = set(EXPECTED_DEPARTMENT_CODES)
    missing_departments = sorted(expected_departments - extracted_departments, key=_department_sort_key)
    unexpected_departments = sorted(extracted_departments - expected_departments, key=_department_sort_key)

    duplicate_keys = [
        "reference_period",
        "departement_code",
        "indicator_code",
        "source_file",
    ]
    duplicate_count = int(curated.duplicated(duplicate_keys).sum())
    null_counts = curated.isna().sum()
    null_counts = {column: int(count) for column, count in null_counts.items() if count > 0}
    suspicious_indicators = sorted(
        value
        for value in curated["indicator_name"].dropna().unique()
        if value not in set(DEPOSITS_REGION_INDICATORS)
    )
    expected_rows_per_source = len(EXPECTED_DEPARTMENT_CODES) * len(DEPOSITS_REGION_INDICATORS)
    rows_per_source = curated.groupby("source_file").size().sort_index()
    incomplete_sources = {
        source_file: int(row_count)
        for source_file, row_count in rows_per_source.items()
        if row_count != expected_rows_per_source
    }
    source_period_mismatches = _source_period_mismatches(curated)

    periods = sorted(curated["reference_period"].dropna().unique())
    missing_months_by_year = _missing_months_by_year(curated)

    return {
        "row_count": int(len(curated)),
        "source_count": int(curated["source_file"].nunique()),
        "department_count": int(len(extracted_departments)),
        "indicator_count": int(curated["indicator_code"].nunique()),
        "periods": periods,
        "missing_departments": missing_departments,
        "unexpected_departments": unexpected_departments,
        "missing_months_by_year": missing_months_by_year,
        "suspicious_indicators": suspicious_indicators,
        "duplicate_count": duplicate_count,
        "null_counts": null_counts,
        "expected_rows_per_source": expected_rows_per_source,
        "incomplete_sources": incomplete_sources,
        "source_period_mismatches": source_period_mismatches,
    }


def build_validation_report(summary: dict) -> str:
    lines = [
        "# Rapport de validation STAT INFO BI",
        "",
        f"- Lignes: {summary['row_count']}",
        f"- Sources PDF: {summary['source_count']}",
        f"- Départements extraits: {summary['department_count']} / {len(EXPECTED_DEPARTMENT_CODES)}",
        f"- Indicateurs: {summary['indicator_count']} / {len(DEPOSITS_REGION_INDICATORS)}",
        f"- Périodes: {', '.join(summary['periods'])}",
        f"- Lignes attendues par source: {summary['expected_rows_per_source']}",
        "",
        "## Départements",
        "",
        _format_list("Manquants", summary["missing_departments"]),
        _format_list("Inattendus", summary["unexpected_departments"]),
        "",
        "## Mois manquants par année",
        "",
    ]
    if summary["missing_months_by_year"]:
        for year, months in summary["missing_months_by_year"].items():
            labels = ", ".join(MONTH_LABELS[month] for month in months)
            lines.append(f"- {year}: {labels}")
    else:
        lines.append("- Aucun")

    lines.extend(
        [
            "",
            "## Indicateurs suspects",
            "",
            _format_list("Indicateurs hors dictionnaire", summary["suspicious_indicators"]),
            "",
            "## Doublons et valeurs nulles",
            "",
            f"- Doublons métier: {summary['duplicate_count']}",
            _format_mapping("Valeurs nulles", summary["null_counts"]),
            "",
            "## Sources incomplètes",
            "",
            _format_mapping("Sources avec nombre de lignes inattendu", summary["incomplete_sources"]),
            "",
            "## Cohérence période / fichier source",
            "",
            _format_mapping("Sources avec période incohérente", summary["source_period_mismatches"]),
            "",
        ]
    )
    return "\n".join(lines)


def build_business_analysis(curated: pd.DataFrame) -> str:
    total = curated[curated["indicator_code"] == "total"].copy()
    monthly_total = (
        total.groupby(["reference_period", "reference_year", "reference_month_number"], as_index=False)["value"]
        .sum()
        .sort_values("reference_period")
        .reset_index(drop=True)
    )
    monthly_total["month_index"] = (
        monthly_total["reference_year"].astype(int) * 12
        + monthly_total["reference_month_number"].astype(int)
    )
    monthly_total["is_consecutive"] = monthly_total["month_index"].diff().eq(1)
    monthly_total["monthly_change"] = monthly_total["value"].diff().where(monthly_total["is_consecutive"])
    monthly_total["monthly_change_pct"] = (
        monthly_total["value"].pct_change().where(monthly_total["is_consecutive"]) * 100
    )

    latest_period = str(monthly_total.iloc[-1]["reference_period"]) if not monthly_total.empty else "n/a"
    latest_total = float(monthly_total.iloc[-1]["value"]) if not monthly_total.empty else 0.0
    first_period = str(monthly_total.iloc[0]["reference_period"]) if not monthly_total.empty else "n/a"
    first_total = float(monthly_total.iloc[0]["value"]) if not monthly_total.empty else 0.0
    period_change = latest_total - first_total
    period_change_pct = (period_change / first_total * 100) if first_total else 0.0

    latest_departments = total[total["reference_period"] == latest_period].sort_values("value", ascending=False)
    top_departments = latest_departments.head(10)[["departement_code", "departement_name", "region", "value"]]
    rupture_table = monthly_total[monthly_total["is_consecutive"]].reindex(
        monthly_total[monthly_total["is_consecutive"]]["monthly_change"].abs().sort_values(ascending=False).index
    ).head(5)
    year_comparison = _build_year_comparison_table(total)

    lines = [
        "# Analyse métier STAT INFO BI",
        "",
        f"- Période couverte: {first_period} à {latest_period}",
        f"- Encours total dernier mois: {latest_total:.1f} Md EUR",
        f"- Variation sur période: {period_change:+.1f} Md EUR ({period_change_pct:+.2f} %)",
        "",
        "## Évolution mensuelle du total",
        "",
        _format_markdown_table(
            monthly_total.assign(
                value=monthly_total["value"].map(lambda value: f"{value:.1f}"),
                monthly_change=monthly_total["monthly_change"].map(_format_signed_float),
                monthly_change_pct=monthly_total["monthly_change_pct"].map(_format_signed_pct),
            ),
            ["reference_period", "value", "monthly_change", "monthly_change_pct"],
        ),
        "",
        "## Plus fortes ruptures mensuelles",
        "",
        _format_markdown_table(
            rupture_table.assign(
                value=rupture_table["value"].map(lambda value: f"{value:.1f}"),
                monthly_change=rupture_table["monthly_change"].map(_format_signed_float),
                monthly_change_pct=rupture_table["monthly_change_pct"].map(_format_signed_pct),
            ),
            ["reference_period", "value", "monthly_change", "monthly_change_pct"],
        ),
        "",
        "## Top départements sur le dernier mois",
        "",
        _format_markdown_table(
            top_departments.assign(value=top_departments["value"].map(lambda value: f"{value:.1f}")),
            ["departement_code", "departement_name", "region", "value"],
        ),
        "",
        "## Comparaison 2025-2026",
        "",
        _build_year_comparison_note(total),
        "",
        _format_markdown_table(year_comparison, list(year_comparison.columns)),
        "",
    ]
    return "\n".join(lines)


def run_quality_pipeline(
    input_csv: Path = DEFAULT_INPUT_CSV,
    curated_csv: Path = DEFAULT_CURATED_CSV,
    indicator_dictionary_csv: Path = DEFAULT_INDICATOR_DICTIONARY_CSV,
    validation_report: Path = DEFAULT_VALIDATION_REPORT,
    business_report: Path = DEFAULT_BUSINESS_REPORT,
) -> dict:
    df = pd.read_csv(input_csv, dtype={"departement_code": str})
    curated = curate_bi_frame(df)
    indicator_dictionary = build_indicator_dictionary()
    summary = build_validation_summary(curated)

    for path in [curated_csv, indicator_dictionary_csv, validation_report, business_report]:
        path.parent.mkdir(parents=True, exist_ok=True)

    curated.to_csv(curated_csv, index=False)
    indicator_dictionary.to_csv(indicator_dictionary_csv, index=False)
    validation_report.write_text(build_validation_report(summary), encoding="utf-8")
    business_report.write_text(build_business_analysis(curated), encoding="utf-8")
    return summary


def _standardize_department_code(value: object) -> str:
    text = str(value).strip().upper()
    if re.fullmatch(r"\d+", text):
        return text.zfill(2)
    return text


def _standardize_indicator_name(value: object) -> str:
    text = str(value).strip()
    normalized = _normalize_text(text)
    for indicator in DEPOSITS_REGION_INDICATORS:
        if _normalize_text(indicator) == normalized:
            return indicator
    return text


def _normalize_month_text(value: object) -> str:
    text = _normalize_text(str(value))
    return text


def _normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.lower())
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", ascii_text).strip()


def _missing_months_by_year(curated: pd.DataFrame) -> dict[int, list[int]]:
    result = {}
    for year, group in curated.groupby("reference_year"):
        observed = set(group["reference_month_number"].dropna().astype(int))
        missing = sorted(set(range(1, 13)) - observed)
        if missing:
            result[int(year)] = missing
    return result


def _format_list(label: str, values: Iterable[str]) -> str:
    values = list(values)
    if not values:
        return f"- {label}: aucun"
    return f"- {label}: {', '.join(values)}"


def _format_mapping(label: str, values: dict) -> str:
    if not values:
        return f"- {label}: aucun"
    formatted = ", ".join(f"{key}={value}" for key, value in values.items())
    return f"- {label}: {formatted}"


def _format_markdown_table(df: pd.DataFrame, columns: list[str]) -> str:
    if df.empty:
        return "_Aucune donnée._"
    selected = df[columns].astype(str)
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join(["---"] * len(columns)) + " |"
    rows = ["| " + " | ".join(row) + " |" for row in selected.to_numpy()]
    return "\n".join([header, separator, *rows])


def _format_signed_float(value: float) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{value:+.1f}"


def _format_signed_pct(value: float) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{value:+.2f} %"


def _build_year_comparison_note(total: pd.DataFrame) -> str:
    year_months = {
        int(year): set(group["reference_month_number"].dropna().astype(int))
        for year, group in total.groupby("reference_year")
    }
    common_months = set.intersection(*year_months.values()) if len(year_months) >= 2 else set()
    if not common_months:
        return (
            "Pas de comparaison annuelle mois à mois fiable dans l'extrait actuel: "
            "les mois 2025 et 2026 disponibles ne se recouvrent pas."
        )
    labels = ", ".join(MONTH_LABELS[month] for month in sorted(common_months))
    return f"Mois comparables disponibles: {labels}."


def _build_year_comparison_table(total: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        total.groupby(["reference_year", "reference_month_number"], as_index=False)["value"]
        .sum()
        .pivot(index="reference_month_number", columns="reference_year", values="value")
    )
    if 2025 not in grouped.columns or 2026 not in grouped.columns:
        return pd.DataFrame()

    comparable = grouped.dropna(subset=[2025, 2026]).copy()
    if comparable.empty:
        return pd.DataFrame()

    comparable["variation_2026_vs_2025"] = comparable[2026] - comparable[2025]
    comparable["variation_2026_vs_2025_pct"] = comparable["variation_2026_vs_2025"] / comparable[2025] * 100
    comparable = comparable.reset_index()
    comparable["month"] = comparable["reference_month_number"].map(MONTH_LABELS)
    comparable["2025"] = comparable[2025].map(lambda value: f"{value:.1f}")
    comparable["2026"] = comparable[2026].map(lambda value: f"{value:.1f}")
    comparable["variation_2026_vs_2025"] = comparable["variation_2026_vs_2025"].map(_format_signed_float)
    comparable["variation_2026_vs_2025_pct"] = comparable["variation_2026_vs_2025_pct"].map(_format_signed_pct)
    return comparable[
        ["month", "2025", "2026", "variation_2026_vs_2025", "variation_2026_vs_2025_pct"]
    ]


def _source_period_mismatches(curated: pd.DataFrame) -> dict[str, str]:
    mismatches = {}
    pairs = curated[["source_file", "reference_period"]].drop_duplicates()
    for row in pairs.itertuples(index=False):
        expected_period = _period_from_source_file(row.source_file)
        if expected_period and row.reference_period != expected_period:
            mismatches[row.source_file] = f"{row.reference_period} != {expected_period}"
    return dict(sorted(mismatches.items()))


def _period_from_source_file(source_file: str) -> str | None:
    match = re.search(r"(20\d{2})(0[1-9]|1[0-2])", source_file)
    if not match:
        return None
    return f"{match.group(1)}-{match.group(2)}"


def _department_sort_key(code: str) -> tuple[int, str]:
    if code in {"2A", "2B"}:
        return (20, code)
    if code.isdigit():
        return (int(code), code)
    return (999, code)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build curated STAT INFO BI data and reports.")
    parser.add_argument("--input-csv", default=str(DEFAULT_INPUT_CSV))
    parser.add_argument("--curated-csv", default=str(DEFAULT_CURATED_CSV))
    parser.add_argument("--indicator-dictionary-csv", default=str(DEFAULT_INDICATOR_DICTIONARY_CSV))
    parser.add_argument("--validation-report", default=str(DEFAULT_VALIDATION_REPORT))
    parser.add_argument("--business-report", default=str(DEFAULT_BUSINESS_REPORT))
    return parser


def main() -> None:
    args = _build_arg_parser().parse_args()
    summary = run_quality_pipeline(
        input_csv=Path(args.input_csv),
        curated_csv=Path(args.curated_csv),
        indicator_dictionary_csv=Path(args.indicator_dictionary_csv),
        validation_report=Path(args.validation_report),
        business_report=Path(args.business_report),
    )
    print(
        "STAT INFO BI quality pipeline completed | "
        f"rows={summary['row_count']} "
        f"departments={summary['department_count']} "
        f"indicators={summary['indicator_count']} "
        f"duplicates={summary['duplicate_count']}"
    )


if __name__ == "__main__":
    main()
