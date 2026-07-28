"""Idempotent import of official INSEE Filosofi territorial indicators."""

from __future__ import annotations

import csv
import hashlib
import io
import math
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from src.risk_score.config import seed_model_1_1
from src.storage.database import get_session_factory
from src.storage.models import (
    InclusionIndicator,
    InclusionObservation,
    InclusionSourceDocument,
)

IMPORT_VERSION = "risk-score-filosofi-v1"
OFFICIAL_URL = (
    "https://www.insee.fr/fr/statistiques/fichier/7756729/"
    "base-cc-filosofi-2021-geo2025_csv.zip"
)
DATA_MEMBER = "DS_FILOSOFI_CC_data.csv"
MEASURES = {
    "PR_MD60": ("taux_pauvrete", "Taux de pauvreté au seuil de 60 %", "%"),
    "MED_SL": (
        "revenu_median",
        "Médiane du niveau de vie annuel",
        "euros",
    ),
}


@dataclass(slots=True)
class FilosofiReport:
    import_version: str = IMPORT_VERSION
    source_year: int | None = None
    source_sha256: str = ""
    periods: int = 0
    department_observations: int = 0
    region_observations: int = 0
    inserted: int = 0
    unchanged: int = 0
    skipped: int = 0


def import_filosofi(
    source_zip: Path,
    *,
    dry_run: bool = False,
    factory: sessionmaker | None = None,
) -> FilosofiReport:
    """Import published, non-summable department and region values."""
    if not source_zip.exists():
        raise FileNotFoundError(f"Filosofi archive not found: {source_zip}")
    source_sha = hashlib.sha256(source_zip.read_bytes()).hexdigest()
    rows = _read_rows(source_zip)
    years = {row["year"] for row in rows}
    if len(years) != 1:
        raise ValueError(f"Expected one Filosofi year, got {sorted(years)}")

    report = FilosofiReport(
        source_year=next(iter(years)),
        source_sha256=source_sha,
    )
    destination_factory = factory or get_session_factory()
    with destination_factory() as session:
        periods = list(
            session.execute(
                select(InclusionObservation.reference_period)
                .where(
                    InclusionObservation.reference_period
                    >= f"{report.source_year:04d}-01"
                )
                .distinct()
                .order_by(InclusionObservation.reference_period)
            ).scalars()
        )
        report.periods = len(periods)
        indicators = _ensure_indicators(session)
        territory_universe = _territory_universe(session)
        for row in rows:
            level = row["level"]
            if row["geographic_code"] not in territory_universe[level]:
                report.skipped += 1
                continue
            for period in periods:
                inserted = _store(
                    session,
                    indicator=indicators[row["indicator_code"]],
                    period=period,
                    level=level,
                    geographic_code=row["geographic_code"],
                    geographic_name=territory_universe[level][
                        row["geographic_code"]
                    ],
                    value=row["value"],
                    unit=row["unit"],
                    source_year=row["year"],
                    source_sha=source_sha,
                    dry_run=dry_run,
                )
                if level == "department":
                    report.department_observations += 1
                else:
                    report.region_observations += 1
                if inserted:
                    report.inserted += 1
                else:
                    report.unchanged += 1
        seed_model_1_1(session)
        if dry_run:
            session.rollback()
        else:
            session.commit()
    return report


def _read_rows(source_zip: Path) -> list[dict]:
    rows = []
    with zipfile.ZipFile(source_zip) as archive:
        if DATA_MEMBER not in archive.namelist():
            raise ValueError(f"Missing Filosofi member: {DATA_MEMBER}")
        with archive.open(DATA_MEMBER) as raw:
            reader = csv.DictReader(
                io.TextIOWrapper(raw, encoding="utf-8-sig"),
                delimiter=";",
            )
            for source in reader:
                if source["GEO_OBJECT"] not in {"DEP", "REG"}:
                    continue
                if source["FILOSOFI_MEASURE"] not in MEASURES:
                    continue
                value = _finite_float(source["OBS_VALUE"])
                if value is None or source["CONF_STATUS"] != "F":
                    continue
                code, label, unit = MEASURES[source["FILOSOFI_MEASURE"]]
                rows.append(
                    {
                        "year": int(source["TIME_PERIOD"]),
                        "level": (
                            "department"
                            if source["GEO_OBJECT"] == "DEP"
                            else "region"
                        ),
                        "geographic_code": source["GEO"],
                        "geographic_name": source["GEO"],
                        "indicator_code": code,
                        "indicator_label": label,
                        "unit": unit,
                        "value": value,
                    }
                )
    if not rows:
        raise ValueError("No publishable Filosofi poverty/income rows found")
    return rows


def _territory_universe(session: Session) -> dict[str, dict[str, str]]:
    return {
        level: {
            str(code): name or str(code)
            for code, name in session.execute(
                select(
                    InclusionObservation.geographic_code,
                    InclusionObservation.geographic_name,
                )
                .where(
                    InclusionObservation.geographic_level == level,
                    InclusionObservation.geographic_code.is_not(None),
                )
                .distinct()
            )
            if code is not None
        }
        for level in ("department", "region")
    }


def _ensure_indicators(session: Session) -> dict[str, InclusionIndicator]:
    codes = {item[0] for item in MEASURES.values()}
    indicators = {
        item.code: item
        for item in session.execute(
            select(InclusionIndicator).where(InclusionIndicator.code.in_(codes))
        ).scalars()
    }
    for code, label, unit in MEASURES.values():
        if code not in indicators:
            item = InclusionIndicator(
                code=code,
                label=label,
                category="filosofi",
                description=(
                    "Valeur territoriale publiée par l'Insee, Filosofi 2021"
                ),
                default_unit=unit,
            )
            session.add(item)
            session.flush()
            indicators[code] = item
    return indicators


def _store(
    session: Session,
    *,
    indicator: InclusionIndicator,
    period: str,
    level: str,
    geographic_code: str,
    geographic_name: str,
    value: float,
    unit: str,
    source_year: int,
    source_sha: str,
    dry_run: bool,
) -> bool:
    identity = (
        f"{IMPORT_VERSION}|{source_sha}|{indicator.code}|{level}|"
        f"{geographic_code}|{period}|{source_year}"
    )
    key = hashlib.sha256(identity.encode()).hexdigest()
    if session.execute(
        select(InclusionObservation.id).where(
            InclusionObservation.idempotence_key == key
        )
    ).scalar_one_or_none():
        return False
    document = _source_document(
        session, period, level, source_year, source_sha
    )
    if not dry_run:
        session.add(
            InclusionObservation(
                source_document_id=document.id,
                indicator_id=indicator.id,
                idempotence_key=key,
                indicator_code=indicator.code,
                region_code=(
                    geographic_code if level == "region" else "FR"
                ),
                reference_period=period,
                geographic_level=level,
                geographic_code=geographic_code,
                geographic_name=geographic_name,
                value_numeric=value,
                unit=unit,
                observation_type="annual_value_propagated_monthly",
                source_label=indicator.label,
                source_fragment=(
                    f"Filosofi measure; annual_source_year={source_year}; "
                    f"source_sha256={source_sha}"
                ),
                extraction_method=IMPORT_VERSION,
                confidence_score=1.0,
            )
        )
    return True


def _source_document(
    session: Session,
    period: str,
    level: str,
    source_year: int,
    source_sha: str,
) -> InclusionSourceDocument:
    identity = f"{IMPORT_VERSION}|{source_sha}|{level}|{period}|{source_year}"
    digest = hashlib.sha256(identity.encode()).hexdigest()
    document = session.execute(
        select(InclusionSourceDocument).where(
            InclusionSourceDocument.pdf_sha256 == digest
        )
    ).scalar_one_or_none()
    if document:
        return document
    document = InclusionSourceDocument(
        source_name="Insee Filosofi",
        publication_type="filosofi_revenus_pauvrete",
        region_code="FR",
        region_name="France",
        reference_period=period,
        publication_date="2025-06-19",
        page_url="https://www.insee.fr/fr/statistiques/7756729",
        pdf_url=OFFICIAL_URL,
        pdf_filename="base-cc-filosofi-2021-geo2025_csv.zip",
        pdf_sha256=digest,
        storage_path=f"remote:{OFFICIAL_URL}#{source_sha}",
        extraction_status="success",
        extractor_version=IMPORT_VERSION,
    )
    session.add(document)
    session.flush()
    return document


def _finite_float(value: str) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def report_as_dict(report: FilosofiReport) -> dict:
    return asdict(report)
