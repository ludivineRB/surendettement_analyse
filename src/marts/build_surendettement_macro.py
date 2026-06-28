"""Build a department-level mart joining Banque de France and INSEE macro data."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

DEFAULT_BDF_CURATED = Path("data/processed/statinfo_departements_bi_curated.csv")
DEFAULT_INSEE_MACRO = Path("data/processed/insee_macro/gold/2026/insee_macro_departements_long.csv")
DEFAULT_OUTPUT = Path("data/processed/marts/departement_surendettement_macro.csv")


def build_surendettement_macro_mart(
    bdf_curated_path: Path = DEFAULT_BDF_CURATED,
    insee_macro_path: Path = DEFAULT_INSEE_MACRO,
    output_path: Path = DEFAULT_OUTPUT,
    macro_reference_year: int | None = None,
) -> pd.DataFrame:
    bdf = pd.read_csv(bdf_curated_path, dtype={"departement_code": str})
    macro = pd.read_csv(insee_macro_path, dtype={"departement_code": str})
    if macro_reference_year is None:
        macro_reference_year = int(macro["reference_year"].max())

    bdf_total = bdf[bdf["indicator_code"] == "total"].copy()
    bdf_total = bdf_total.rename(columns={"value": "bdf_total_deposits_value"})
    bdf_total = bdf_total[
        [
            "reference_period",
            "reference_year",
            "reference_month_number",
            "departement_code",
            "departement_name",
            "region",
            "bdf_total_deposits_value",
        ]
    ]

    macro_year = macro[macro["reference_year"] == macro_reference_year].copy()
    macro_wide = macro_year.pivot_table(
        index=["departement_code"],
        columns="indicator_code",
        values="value",
        aggfunc="first",
    ).reset_index()
    macro_wide.columns = [
        column if column == "departement_code" else f"macro_{column}" for column in macro_wide.columns
    ]
    macro_wide["macro_reference_year"] = macro_reference_year

    mart = bdf_total.merge(macro_wide, on="departement_code", how="left")
    mart["mart_version"] = "departement_surendettement_macro_v1"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mart.to_csv(output_path, index=False)
    return mart


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build Banque de France x INSEE department mart.")
    parser.add_argument("--bdf-curated", default=str(DEFAULT_BDF_CURATED))
    parser.add_argument("--insee-macro", default=str(DEFAULT_INSEE_MACRO))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--macro-reference-year", type=int, default=None)
    return parser


def main() -> None:
    args = _build_arg_parser().parse_args()
    mart = build_surendettement_macro_mart(
        bdf_curated_path=Path(args.bdf_curated),
        insee_macro_path=Path(args.insee_macro),
        output_path=Path(args.output),
        macro_reference_year=args.macro_reference_year,
    )
    print(
        "Department surendettement x macro mart built | "
        f"rows={len(mart)} "
        f"departments={mart['departement_code'].nunique()}"
    )


if __name__ == "__main__":
    main()
