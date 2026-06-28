"""Pipeline for INSEE Base du dossier complet macro-economic data.

The dossier complet is commune-level and wide. This module keeps raw files
separate from Banque de France data, normalizes them to long format, filters
metropolitan departments, and builds department-level aggregates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

import pandas as pd
import requests

from src.statinfo_bi_quality import EXPECTED_DEPARTMENT_CODES

INSEE_DOSSIER_COMPLET_PAGE = "https://www.insee.fr/fr/statistiques/5359146"
PIPELINE_VERSION = "insee_macro_dossier_complet_v1"
CSV_SEPARATOR = ";"

RAW_ROOT = Path("data/raw/insee_macro/dossier_complet")
SILVER_ROOT = Path("data/processed/insee_macro/silver")
GOLD_ROOT = Path("data/processed/insee_macro/gold")
MART_ROOT = Path("data/processed/marts")

GEO_COLUMNS = {
    "CODGEO",
    "LIBGEO",
    "REG",
    "DEP",
    "UU2020",
    "AAV2020",
    "ZE2020",
    "EPCI",
}


@dataclass(slots=True)
class DownloadCandidate:
    url: str
    year: int | None
    filename: str


@dataclass(slots=True)
class PipelinePaths:
    year: int
    raw_dir: Path
    silver_dir: Path
    gold_dir: Path

    @classmethod
    def for_year(cls, year: int) -> "PipelinePaths":
        return cls(
            year=year,
            raw_dir=RAW_ROOT / str(year),
            silver_dir=SILVER_ROOT / str(year),
            gold_dir=GOLD_ROOT / str(year),
        )

    @property
    def manifest_path(self) -> Path:
        return self.raw_dir / "source_manifest.json"

    @property
    def communes_long_csv(self) -> Path:
        return self.silver_dir / "communes_macro_long.csv"

    @property
    def departements_long_csv(self) -> Path:
        return self.gold_dir / "insee_macro_departements_long.csv"

    @property
    def indicator_dictionary_csv(self) -> Path:
        return self.gold_dir / "insee_macro_indicator_dictionary.csv"

    @property
    def quality_report_path(self) -> Path:
        return self.gold_dir / "insee_macro_quality_report.md"


def discover_dossier_complet_downloads(html: str, base_url: str = INSEE_DOSSIER_COMPLET_PAGE) -> list[DownloadCandidate]:
    candidates: list[DownloadCandidate] = []
    hrefs = re.findall(r'href=["\']([^"\']+)["\']', html, flags=re.IGNORECASE)
    for href in hrefs:
        if not re.search(r"\.(csv|zip)(?:$|\?)", href, flags=re.IGNORECASE):
            continue
        absolute_url = urljoin(base_url, href)
        filename = Path(absolute_url.split("?", 1)[0]).name
        if "dossier" not in filename.lower():
            continue
        candidates.append(
            DownloadCandidate(
                url=absolute_url,
                year=_infer_year_from_text(absolute_url),
                filename=filename,
            )
        )
    return _dedupe_candidates(candidates)


def download_latest_or_year(year: int, page_url: str = INSEE_DOSSIER_COMPLET_PAGE) -> Path:
    response = requests.get(page_url, timeout=60)
    response.raise_for_status()
    candidates = discover_dossier_complet_downloads(response.text, base_url=page_url)
    candidate = _select_candidate(candidates, year=year)
    if candidate is None:
        raise RuntimeError(f"No INSEE dossier complet download found for year={year}")

    paths = PipelinePaths.for_year(year)
    paths.raw_dir.mkdir(parents=True, exist_ok=True)
    output_path = paths.raw_dir / candidate.filename
    if not output_path.exists():
        with requests.get(candidate.url, stream=True, timeout=600) as download:
            download.raise_for_status()
            with output_path.open("wb") as output:
                for chunk in download.iter_content(1024 * 1024):
                    if chunk:
                        output.write(chunk)

    manifest = {
        "source": "INSEE",
        "dataset": "base_dossier_complet",
        "publication_page": page_url,
        "download_url": candidate.url,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "target_year": year,
        "filename": output_path.name,
        "file_size_bytes": output_path.stat().st_size,
        "sha256": _sha256(output_path),
        "pipeline_version": PIPELINE_VERSION,
    }
    paths.manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def extract_raw_source(year: int, source_path: Path | None = None) -> Path:
    paths = PipelinePaths.for_year(year)
    paths.raw_dir.mkdir(parents=True, exist_ok=True)
    source_path = source_path or _find_downloaded_source(paths.raw_dir)
    if source_path is None:
        raise FileNotFoundError(f"No downloaded source found in {paths.raw_dir}")

    if source_path.suffix.lower() == ".zip":
        with zipfile.ZipFile(source_path) as archive:
            archive.extractall(paths.raw_dir / "extracted")
        return _find_main_csv(paths.raw_dir / "extracted")

    if source_path.suffix.lower() == ".csv":
        stable_path = paths.raw_dir / "dossier_complet.csv"
        if source_path.resolve() != stable_path.resolve():
            shutil.copy2(source_path, stable_path)
        return stable_path

    raise ValueError(f"Unsupported INSEE source format: {source_path}")


def build_communes_long(year: int, source_csv: Path | None = None, chunksize: int = 25_000) -> pd.DataFrame:
    paths = PipelinePaths.for_year(year)
    source_csv = source_csv or extract_raw_source(year)
    paths.silver_dir.mkdir(parents=True, exist_ok=True)
    paths.gold_dir.mkdir(parents=True, exist_ok=True)

    output_frames = []
    dictionary_parts = []
    for chunk in pd.read_csv(source_csv, sep=CSV_SEPARATOR, decimal=".", chunksize=chunksize, low_memory=False):
        chunk = _normalize_columns(chunk)
        chunk = _ensure_department_code(chunk)
        chunk = chunk[chunk["departement_code"].isin(EXPECTED_DEPARTMENT_CODES)].copy()
        if chunk.empty:
            continue
        value_columns = _value_columns(chunk)
        dictionary_parts.append(_build_indicator_dictionary_from_columns(value_columns))
        id_columns = ["commune_code", "commune_name", "departement_code", "region_code"]
        long_df = chunk[id_columns + value_columns].melt(
            id_vars=id_columns,
            value_vars=value_columns,
            var_name="indicator_code",
            value_name="value",
        )
        long_df["value"] = pd.to_numeric(long_df["value"], errors="coerce")
        long_df = long_df[long_df["value"].notna()].copy()
        long_df["reference_year"] = year
        long_df["geo_level"] = "COM"
        long_df["source_dataset"] = "insee_base_dossier_complet"
        long_df["pipeline_version"] = PIPELINE_VERSION
        output_frames.append(long_df)

    communes = pd.concat(output_frames, ignore_index=True) if output_frames else _empty_communes_long()
    dictionary = (
        pd.concat(dictionary_parts, ignore_index=True).drop_duplicates("indicator_code")
        if dictionary_parts
        else _empty_indicator_dictionary()
    )
    dictionary["indicator_group"] = dictionary["indicator_code"].map(_infer_indicator_group)
    dictionary["aggregation_rule"] = dictionary.apply(
        lambda row: _infer_aggregation_rule(row["indicator_code"], row["indicator_name"]),
        axis=1,
    )
    communes.to_csv(paths.communes_long_csv, index=False)
    dictionary.to_csv(paths.indicator_dictionary_csv, index=False)
    return communes


def aggregate_departements(year: int) -> pd.DataFrame:
    paths = PipelinePaths.for_year(year)
    paths.gold_dir.mkdir(parents=True, exist_ok=True)
    communes = pd.read_csv(paths.communes_long_csv, dtype={"departement_code": str, "commune_code": str})
    dictionary = pd.read_csv(paths.indicator_dictionary_csv)
    enriched = communes.merge(
        dictionary[["indicator_code", "indicator_name", "indicator_group", "aggregation_rule"]],
        on="indicator_code",
        how="left",
    )

    dept_names = _department_names(enriched)
    pieces = []
    for rule, group in enriched.groupby("aggregation_rule", dropna=False):
        grouped = group.groupby(["reference_year", "departement_code", "indicator_code"], as_index=False)
        if rule == "mean":
            aggregated = grouped["value"].mean()
        else:
            aggregated = grouped["value"].sum()
        aggregated["aggregation_rule"] = rule or "sum"
        pieces.append(aggregated)

    departements = pd.concat(pieces, ignore_index=True) if pieces else _empty_departements_long()
    departements = departements.merge(dept_names, on="departement_code", how="left")
    departements = departements.merge(
        dictionary[["indicator_code", "indicator_name", "indicator_group"]],
        on="indicator_code",
        how="left",
    )
    departements["geo_level"] = "DEP"
    departements["source_dataset"] = "insee_base_dossier_complet"
    departements["pipeline_version"] = PIPELINE_VERSION
    departements = departements[
        [
            "reference_year",
            "geo_level",
            "departement_code",
            "departement_name",
            "indicator_code",
            "indicator_name",
            "indicator_group",
            "aggregation_rule",
            "value",
            "source_dataset",
            "pipeline_version",
        ]
    ].sort_values(["reference_year", "departement_code", "indicator_code"])
    departements.to_csv(paths.departements_long_csv, index=False)
    return departements


def build_quality_report(year: int) -> str:
    paths = PipelinePaths.for_year(year)
    departements = pd.read_csv(paths.departements_long_csv, dtype={"departement_code": str})
    observed_departments = set(departements["departement_code"].dropna().unique())
    missing_departments = sorted(set(EXPECTED_DEPARTMENT_CODES) - observed_departments)
    unexpected_departments = sorted(observed_departments - set(EXPECTED_DEPARTMENT_CODES))
    duplicate_count = int(
        departements.duplicated(["reference_year", "departement_code", "indicator_code"]).sum()
    )
    null_values = int(departements["value"].isna().sum())
    report = "\n".join(
        [
            "# Rapport qualité INSEE macro",
            "",
            f"- Année cible: {year}",
            f"- Lignes départementales: {len(departements)}",
            f"- Départements: {len(observed_departments)} / {len(EXPECTED_DEPARTMENT_CODES)}",
            f"- Indicateurs: {departements['indicator_code'].nunique()}",
            f"- Doublons métier: {duplicate_count}",
            f"- Valeurs nulles: {null_values}",
            f"- Départements manquants: {', '.join(missing_departments) if missing_departments else 'aucun'}",
            f"- Départements inattendus: {', '.join(unexpected_departments) if unexpected_departments else 'aucun'}",
            "",
            "## Règles d'agrégation",
            "",
            departements.groupby("aggregation_rule")["indicator_code"].nunique().to_string(),
            "",
        ]
    )
    paths.quality_report_path.write_text(report, encoding="utf-8")
    return report


def run_pipeline(year: int, source_csv: Path | None = None, skip_download: bool = False) -> None:
    if not skip_download and source_csv is None:
        download_latest_or_year(year)
    extracted = extract_raw_source(year, source_path=source_csv) if source_csv else extract_raw_source(year)
    build_communes_long(year, source_csv=extracted)
    aggregate_departements(year)
    build_quality_report(year)


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    renamed = {column: str(column).strip() for column in df.columns}
    df = df.rename(columns=renamed).copy()
    code_col = _first_existing(df.columns, ["CODGEO", "COM", "commune_code"])
    label_col = _first_existing(df.columns, ["LIBGEO", "LIBCOM", "commune_name"])
    dep_col = _first_existing(df.columns, ["DEP", "departement_code"])
    reg_col = _first_existing(df.columns, ["REG", "region_code"])
    if code_col is None:
        raise ValueError("Cannot find commune code column in INSEE dossier complet")
    df["commune_code"] = df[code_col].astype(str).str.strip()
    df["commune_name"] = df[label_col].astype(str).str.strip() if label_col else pd.NA
    df["departement_code"] = df[dep_col].map(_standardize_department_code) if dep_col else pd.NA
    df["region_code"] = df[reg_col].astype(str).str.strip() if reg_col else pd.NA
    return df


def _ensure_department_code(df: pd.DataFrame) -> pd.DataFrame:
    missing = df["departement_code"].isna()
    if missing.any():
        df.loc[missing, "departement_code"] = df.loc[missing, "commune_code"].map(_department_from_commune)
    return df


def _department_from_commune(commune_code: str) -> str:
    code = str(commune_code).strip().upper()
    if code.startswith(("2A", "2B")):
        return code[:2]
    return code[:2]


def _standardize_department_code(value: object) -> str:
    text = str(value).strip().upper()
    return text.zfill(2) if text.isdigit() else text


def _value_columns(df: pd.DataFrame) -> list[str]:
    excluded = set(GEO_COLUMNS) | {"commune_code", "commune_name", "departement_code", "region_code"}
    candidates = [column for column in df.columns if column not in excluded]
    return [column for column in candidates if pd.to_numeric(df[column], errors="coerce").notna().any()]


def _build_indicator_dictionary_from_columns(columns: Iterable[str]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "indicator_code": column,
                "indicator_name": column,
            }
            for column in columns
        ]
    )


def _infer_indicator_group(indicator_code: str) -> str:
    code = indicator_code.upper()
    if "POP" in code or "NAIS" in code or "DECE" in code:
        return "démographie"
    if "LOG" in code or "MEN" in code:
        return "logement_ménages"
    if "DIPL" in code or "SCOL" in code:
        return "formation"
    if "ACT" in code or "EMP" in code or "CHOM" in code:
        return "emploi_chômage"
    if "REV" in code or "PAUV" in code or "SAL" in code:
        return "revenus"
    if "ENT" in code or "ETAB" in code:
        return "entreprises"
    return "autre"


def _infer_aggregation_rule(indicator_code: str, indicator_name: str) -> str:
    text = f"{indicator_code} {indicator_name}".lower()
    if any(token in text for token in ["tx", "taux", "part", "pct", "moy", "med", "méd"]):
        return "mean"
    return "sum"


def _department_names(communes: pd.DataFrame) -> pd.DataFrame:
    names = communes[["departement_code"]].drop_duplicates().copy()
    names["departement_name"] = pd.NA
    return names


def _find_downloaded_source(raw_dir: Path) -> Path | None:
    candidates = sorted([*raw_dir.glob("*.csv"), *raw_dir.glob("*.zip")])
    return candidates[0] if candidates else None


def _find_main_csv(directory: Path) -> Path:
    csvs = [path for path in directory.rglob("*.csv") if "meta" not in path.name.lower()]
    if not csvs:
        raise FileNotFoundError(f"No main CSV found in {directory}")
    return max(csvs, key=lambda path: path.stat().st_size)


def _select_candidate(candidates: list[DownloadCandidate], year: int) -> DownloadCandidate | None:
    exact = [candidate for candidate in candidates if candidate.year == year]
    if exact:
        return exact[0]
    if candidates and year == datetime.now().year:
        return candidates[0]
    return None


def _dedupe_candidates(candidates: list[DownloadCandidate]) -> list[DownloadCandidate]:
    deduped = {}
    for candidate in candidates:
        deduped[candidate.url] = candidate
    return list(deduped.values())


def _infer_year_from_text(text: str) -> int | None:
    years = [int(match) for match in re.findall(r"20\d{2}", text)]
    return max(years) if years else None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _first_existing(columns: Iterable[str], candidates: list[str]) -> str | None:
    columns_set = set(columns)
    for candidate in candidates:
        if candidate in columns_set:
            return candidate
    return None


def _empty_communes_long() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "commune_code",
            "commune_name",
            "departement_code",
            "region_code",
            "indicator_code",
            "value",
            "reference_year",
            "geo_level",
            "source_dataset",
            "pipeline_version",
        ]
    )


def _empty_departements_long() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "reference_year",
            "departement_code",
            "indicator_code",
            "value",
            "aggregation_rule",
        ]
    )


def _empty_indicator_dictionary() -> pd.DataFrame:
    return pd.DataFrame(columns=["indicator_code", "indicator_name", "indicator_group", "aggregation_rule"])


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="INSEE dossier complet macro pipeline.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ["download", "extract", "transform", "aggregate", "quality", "run"]:
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--year", type=int, required=True)
        subparser.add_argument("--source-csv", default=None)
        if command == "run":
            subparser.add_argument("--skip-download", action="store_true")

    return parser


def main() -> None:
    args = _build_arg_parser().parse_args()
    source_csv = Path(args.source_csv) if getattr(args, "source_csv", None) else None
    if args.command == "download":
        path = download_latest_or_year(args.year)
        print(f"Downloaded: {path}")
    elif args.command == "extract":
        path = extract_raw_source(args.year, source_path=source_csv)
        print(f"Extracted source CSV: {path}")
    elif args.command == "transform":
        df = build_communes_long(args.year, source_csv=source_csv)
        print(f"Communes long rows: {len(df)}")
    elif args.command == "aggregate":
        df = aggregate_departements(args.year)
        print(f"Department rows: {len(df)}")
    elif args.command == "quality":
        print(build_quality_report(args.year))
    elif args.command == "run":
        run_pipeline(args.year, source_csv=source_csv, skip_download=args.skip_download)
        print(f"INSEE macro pipeline completed for year={args.year}")


if __name__ == "__main__":
    main()
