"""Versioned import of national monthly inflation from the official INSEE BDM API."""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass

import requests
from sqlalchemy import select

from src.storage.database import get_session_factory
from src.storage.models import (
    InclusionIndicator,
    InclusionObservation,
    InclusionSourceDocument,
    RiskScoreIndicatorConfig,
    RiskScoreModel,
)

IMPORT_VERSION = "risk-score-insee-inflation-v1"
SERIES_ID = "011814630"
SERIES_PAGE = f"https://www.insee.fr/fr/statistiques/serie/{SERIES_ID}"
SERIES_API = (
    f"https://api.insee.fr/series/BDM/V1/data/SERIES_BDM/{SERIES_ID}"
)


@dataclass(slots=True)
class InflationImportReport:
    series_id: str = SERIES_ID
    periods_available: int = 0
    observations_inserted: int = 0
    observations_unchanged: int = 0
    model_mapped: bool = False


def parse_insee_series(xml_content: bytes) -> dict[str, float]:
    """Extract monthly index values from a structure-specific SDMX response."""
    values: dict[str, float] = {}
    root = ET.fromstring(xml_content)
    for observation in root.iter():
        if observation.tag.rsplit("}", 1)[-1] != "Obs":
            continue
        period = observation.attrib.get("TIME_PERIOD")
        raw_value = observation.attrib.get("OBS_VALUE")
        if period and raw_value and len(period) == 7:
            values[period] = float(raw_value)
    return values


def year_on_year_rates(indexes: dict[str, float]) -> dict[str, float]:
    rates = {}
    for period, value in indexes.items():
        previous = f"{int(period[:4]) - 1:04d}-{period[5:]}"
        if previous in indexes and indexes[previous] != 0:
            rates[period] = (value / indexes[previous] - 1.0) * 100.0
    return rates


def annual_average_rates(monthly_rates: dict[str, float]) -> dict[str, float]:
    grouped: dict[str, list[float]] = {}
    for period, value in monthly_rates.items():
        grouped.setdefault(period[:4], []).append(value)
    return {
        year: sum(values) / len(values)
        for year, values in grouped.items()
        if values
    }


def import_inflation(
    *,
    xml_content: bytes | None = None,
    dry_run: bool = False,
) -> InflationImportReport:
    if xml_content is None:
        response = requests.get(SERIES_API, timeout=60)
        response.raise_for_status()
        xml_content = response.content
    monthly_rates = year_on_year_rates(parse_insee_series(xml_content))
    rates = {**monthly_rates, **annual_average_rates(monthly_rates)}
    report = InflationImportReport(periods_available=len(rates))
    factory = get_session_factory()
    with factory() as session:
        indicator = session.execute(
            select(InclusionIndicator).where(InclusionIndicator.code == "inflation")
        ).scalar_one_or_none()
        if indicator is None:
            indicator = InclusionIndicator(
                code="inflation",
                label="Inflation en glissement annuel",
                category="macroeconomie",
                description=(
                    "Variation sur douze mois de l'IPC France, répliquée à "
                    "l'identique entre territoires pour la comparaison temporelle."
                ),
                default_unit="%",
            )
            session.add(indicator)
            session.flush()

        territories = session.execute(
            select(
                InclusionObservation.geographic_level,
                InclusionObservation.geographic_code,
                InclusionObservation.geographic_name,
                InclusionObservation.reference_period,
            )
            .where(
                InclusionObservation.geographic_level.in_(("region", "department")),
                InclusionObservation.geographic_code.is_not(None),
            )
            .distinct()
        )
        documents: dict[str, InclusionSourceDocument] = {}
        for level, code, name, period in territories:
            if period not in rates:
                continue
            document = documents.get(period)
            if document is None:
                document = _source_document(session, period, xml_content)
                documents[period] = document
            key = hashlib.sha256(
                f"{IMPORT_VERSION}|{level}|{code}|{period}".encode()
            ).hexdigest()
            exists = session.execute(
                select(InclusionObservation.id).where(
                    InclusionObservation.idempotence_key == key
                )
            ).scalar_one_or_none()
            if exists:
                report.observations_unchanged += 1
                continue
            session.add(
                InclusionObservation(
                    source_document_id=document.id,
                    indicator_id=indicator.id,
                    idempotence_key=key,
                    indicator_code="inflation",
                    region_code=str(code) if level == "region" else "FR",
                    reference_period=period,
                    geographic_level=level,
                    geographic_code=str(code),
                    geographic_name=name,
                    value_numeric=rates[period],
                    unit="%",
                    observation_type="national_monthly_replicated",
                    comparison_period=f"{int(period[:4]) - 1:04d}-{period[5:]}",
                    source_label="IPC France — glissement annuel",
                    source_fragment=f"INSEE series={SERIES_ID}; import={IMPORT_VERSION}",
                    extraction_method=IMPORT_VERSION,
                    confidence_score=1.0,
                )
            )
            report.observations_inserted += 1

        models = session.execute(
            select(RiskScoreModel).where(RiskScoreModel.code == "default")
        ).scalars()
        for model in models:
            config = session.execute(
                select(RiskScoreIndicatorConfig).where(
                    RiskScoreIndicatorConfig.risk_score_model_id == model.id,
                    RiskScoreIndicatorConfig.logical_code == "inflation",
                )
            ).scalar_one_or_none()
            if config:
                config.indicator_id = indicator.id
                config.indicator_code = indicator.code
                report.model_mapped = True
        if dry_run:
            session.rollback()
        else:
            session.commit()
    return report


def _source_document(
    session, period: str, xml_content: bytes
) -> InclusionSourceDocument:
    digest = hashlib.sha256(
        xml_content + f"|{IMPORT_VERSION}|{period}".encode()
    ).hexdigest()
    existing = session.execute(
        select(InclusionSourceDocument).where(
            InclusionSourceDocument.pdf_sha256 == digest
        )
    ).scalar_one_or_none()
    if existing:
        return existing
    document = InclusionSourceDocument(
        source_name="INSEE",
        publication_type="ipc_national_monthly",
        region_code="FR",
        region_name="France",
        reference_period=period,
        page_url=SERIES_PAGE,
        pdf_url=SERIES_API,
        pdf_filename=f"insee-{SERIES_ID}-{period}.xml",
        pdf_sha256=digest,
        storage_path=SERIES_API,
        extraction_status="success",
        extractor_version=IMPORT_VERSION,
    )
    session.add(document)
    session.flush()
    return document


def report_as_dict(report: InflationImportReport) -> dict:
    return asdict(report)
