"""Versioned, idempotent bridge from the analytics mart to score observations."""

from __future__ import annotations

import hashlib
import math
import sqlite3
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

BRIDGE_VERSION = "risk-score-analytics-bridge-v1"
DEFAULT_ANALYTICS_DB = Path(
    "data/processed/analytics/surendettement_macro_analytics.db"
)

REGION_CODES = {
    "Île-de-France": "11",
    "Centre-Val de Loire": "24",
    "Bourgogne-Franche-Comté": "27",
    "Normandie": "28",
    "Hauts-de-France": "32",
    "Grand Est": "44",
    "Pays de la Loire": "52",
    "Bretagne": "53",
    "Nouvelle-Aquitaine": "75",
    "Occitanie": "76",
    "Auvergne-Rhône-Alpes": "84",
    "Provence-Alpes-Côte d’Azur": "93",
    "Corse": "94",
}

INDICATORS = {
    "dossiers_surendettement_1000_habitants": (
        "Dossiers de surendettement déposés pour 1 000 habitants",
        "dossiers_pour_1000_habitants",
    ),
    "taux_chomage": ("Taux de chômage des 15 à 64 ans", "%"),
}


@dataclass(slots=True)
class BridgeReport:
    bridge_version: str = BRIDGE_VERSION
    periods: int = 0
    department_observations: int = 0
    region_observations: int = 0
    inserted: int = 0
    unchanged: int = 0
    skipped: int = 0


def import_analytics_indicators(
    analytics_db: Path = DEFAULT_ANALYTICS_DB,
    *,
    dry_run: bool = False,
    factory: sessionmaker | None = None,
) -> BridgeReport:
    """Derive comparable monthly observations without overwriting source data."""
    if not analytics_db.exists():
        raise FileNotFoundError(f"Analytics database not found: {analytics_db}")
    destination_factory = factory or get_session_factory()
    report = BridgeReport()
    with sqlite3.connect(f"file:{analytics_db}?mode=ro", uri=True) as source:
        source.row_factory = sqlite3.Row
        macro = _load_macro(source)
    with destination_factory() as session:
        periods = list(
            session.execute(
                select(InclusionObservation.reference_period)
                .where(
                    InclusionObservation.geographic_level == "region",
                    InclusionObservation.indicator_code
                    == "surendettement_dossiers_deposes",
                )
                .distinct()
                .order_by(InclusionObservation.reference_period)
            ).scalars()
        )
        report.periods = len(periods)
        indicators = _ensure_indicators(session)
        for period in periods:
            annual = _latest_macro_for_period(macro, period)
            if not annual:
                report.skipped += 1
                continue
            for row in annual.values():
                value = _ratio(row["unemployed"], row["active"], 100.0)
                if value is None:
                    report.skipped += 1
                    continue
                inserted = _store_observation(
                    session,
                    indicators["taux_chomage"],
                    period=period,
                    level="department",
                    geographic_code=row["department_code"],
                    geographic_name=row["department_name"],
                    region_code=row["region_code"],
                    value=value,
                    unit="%",
                    source_year=row["year"],
                    formula="P22_CHOM1564 / P22_ACT1564 * 100",
                    dry_run=dry_run,
                )
                report.department_observations += 1
                _count(report, inserted)

            for region in _aggregate_regions(annual).values():
                unemployment = _ratio(
                    region["unemployed"], region["active"], 100.0
                )
                if unemployment is not None:
                    inserted = _store_observation(
                        session,
                        indicators["taux_chomage"],
                        period=period,
                        level="region",
                        geographic_code=region["region_code"],
                        geographic_name=region["region_name"],
                        region_code=region["region_code"],
                        value=unemployment,
                        unit="%",
                        source_year=region["year"],
                        formula="sum(P22_CHOM1564) / sum(P22_ACT1564) * 100",
                        dry_run=dry_run,
                    )
                    report.region_observations += 1
                    _count(report, inserted)
                dossiers = _regional_dossiers(
                    session, region["region_code"], period
                )
                rate = _ratio(dossiers, region["population"], 1000.0)
                if rate is not None:
                    inserted = _store_observation(
                        session,
                        indicators[
                            "dossiers_surendettement_1000_habitants"
                        ],
                        period=period,
                        level="region",
                        geographic_code=region["region_code"],
                        geographic_name=region["region_name"],
                        region_code=region["region_code"],
                        value=rate,
                        unit="dossiers_pour_1000_habitants",
                        source_year=region["year"],
                        formula=(
                            "dossiers_mensuels / "
                            "sum(P22_POP) * 1000"
                        ),
                        dry_run=dry_run,
                    )
                    report.region_observations += 1
                    _count(report, inserted)
        seed_model_1_1(session)
        if not dry_run:
            session.commit()
        else:
            session.rollback()
    return report


def _load_macro(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT f.reference_year, f.departement_code, d.departement_name,
               d.region_name, i.indicator_code, f.value
        FROM fact_insee_macro f
        JOIN dim_department d USING (departement_code)
        JOIN dim_indicator i USING (indicator_key)
        WHERE i.indicator_code IN ('P22_POP', 'P22_ACT1564', 'P22_CHOM1564')
          AND d.is_metropolitan_scope = 1
        """
    ).fetchall()


def _latest_macro_for_period(
    rows: list[sqlite3.Row], period: str
) -> dict[str, dict]:
    target_year = int(period[:4])
    years = sorted(
        {int(row["reference_year"]) for row in rows if row["reference_year"] <= target_year}
    )
    if not years:
        return {}
    selected_year = years[-1]
    departments: dict[str, dict] = {}
    for row in rows:
        if int(row["reference_year"]) != selected_year:
            continue
        region_name = row["region_name"]
        region_code = REGION_CODES.get(region_name)
        if not region_code:
            continue
        item = departments.setdefault(
            row["departement_code"],
            {
                "year": selected_year,
                "department_code": row["departement_code"],
                "department_name": row["departement_name"],
                "region_code": region_code,
                "region_name": region_name,
            },
        )
        aliases = {
            "P22_POP": "population",
            "P22_ACT1564": "active",
            "P22_CHOM1564": "unemployed",
        }
        item[aliases[row["indicator_code"]]] = float(row["value"])
    return departments


def _aggregate_regions(departments: dict[str, dict]) -> dict[str, dict]:
    regions: dict[str, dict] = {}
    for department in departments.values():
        code = department["region_code"]
        region = regions.setdefault(
            code,
            {
                "year": department["year"],
                "region_code": code,
                "region_name": department["region_name"],
                "population": 0.0,
                "active": 0.0,
                "unemployed": 0.0,
            },
        )
        for field in ("population", "active", "unemployed"):
            region[field] += float(department.get(field, 0.0))
    return regions


def _ensure_indicators(session: Session) -> dict[str, InclusionIndicator]:
    existing = {
        item.code: item
        for item in session.execute(
            select(InclusionIndicator).where(
                InclusionIndicator.code.in_(INDICATORS)
            )
        ).scalars()
    }
    for code, (label, unit) in INDICATORS.items():
        if code not in existing:
            item = InclusionIndicator(
                code=code,
                label=label,
                category="risk_score_derived",
                description=f"Indicateur dérivé par {BRIDGE_VERSION}",
                default_unit=unit,
            )
            session.add(item)
            session.flush()
            existing[code] = item
    return existing


def _regional_dossiers(
    session: Session, region_code: str, period: str
) -> float | None:
    value = session.execute(
        select(InclusionObservation.value_numeric)
        .where(
            InclusionObservation.geographic_level == "region",
            InclusionObservation.geographic_code == region_code,
            InclusionObservation.reference_period == period,
            InclusionObservation.indicator_code
            == "surendettement_dossiers_deposes",
        )
        .order_by(
            InclusionObservation.confidence_score.desc().nullslast(),
            InclusionObservation.updated_at.desc(),
            InclusionObservation.id.desc(),
        )
    ).scalars().first()
    return float(value) if value is not None else None


def _store_observation(
    session: Session,
    indicator: InclusionIndicator,
    *,
    period: str,
    level: str,
    geographic_code: str,
    geographic_name: str,
    region_code: str,
    value: float,
    unit: str,
    source_year: int,
    formula: str,
    dry_run: bool,
) -> bool:
    identity = (
        f"{BRIDGE_VERSION}|{indicator.code}|{level}|"
        f"{geographic_code}|{period}|{source_year}"
    )
    key = hashlib.sha256(identity.encode()).hexdigest()
    if session.execute(
        select(InclusionObservation.id).where(
            InclusionObservation.idempotence_key == key
        )
    ).scalar_one_or_none():
        return False
    document = _bridge_document(session, period, level, source_year)
    if not dry_run:
        session.add(
            InclusionObservation(
                source_document_id=document.id,
                indicator_id=indicator.id,
                idempotence_key=key,
                indicator_code=indicator.code,
                region_code=region_code,
                reference_period=period,
                geographic_level=level,
                geographic_code=geographic_code,
                geographic_name=geographic_name,
                value_numeric=value,
                unit=unit,
                observation_type="derived_monthly_from_annual",
                source_label=formula,
                source_fragment=(
                    f"annual_source_year={source_year}; "
                    f"bridge_version={BRIDGE_VERSION}"
                ),
                extraction_method=BRIDGE_VERSION,
                confidence_score=1.0,
            )
        )
    return True


def _bridge_document(
    session: Session, period: str, level: str, source_year: int
) -> InclusionSourceDocument:
    identity = f"{BRIDGE_VERSION}|{level}|{period}|{source_year}"
    digest = hashlib.sha256(identity.encode()).hexdigest()
    existing = session.execute(
        select(InclusionSourceDocument).where(
            InclusionSourceDocument.pdf_sha256 == digest
        )
    ).scalar_one_or_none()
    if existing:
        return existing
    document = InclusionSourceDocument(
        source_name="INSEE + Banque de France",
        publication_type="risk_score_derived_indicators",
        region_code="FR",
        region_name="France métropolitaine",
        reference_period=period,
        page_url="internal://analytics-bridge",
        pdf_url="internal://analytics-bridge",
        pdf_filename=f"{BRIDGE_VERSION}-{level}-{period}.json",
        pdf_sha256=digest,
        storage_path=str(DEFAULT_ANALYTICS_DB),
        extraction_status="success",
        extractor_version=BRIDGE_VERSION,
    )
    session.add(document)
    session.flush()
    return document


def _ratio(
    numerator: float | None, denominator: float | None, multiplier: float
) -> float | None:
    if numerator is None or denominator is None:
        return None
    if not math.isfinite(numerator) or not math.isfinite(denominator):
        return None
    if denominator <= 0:
        return None
    return numerator / denominator * multiplier


def _count(report: BridgeReport, inserted: bool) -> None:
    if inserted:
        report.inserted += 1
    else:
        report.unchanged += 1


def report_as_dict(report: BridgeReport) -> dict:
    return asdict(report)
