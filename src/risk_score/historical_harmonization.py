"""Harmonize annual department context for historical score calculation."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass

import requests
from sqlalchemy import select

from src.risk_score.department_debt_import import (
    IMPORT_VERSION as DEPARTMENT_IMPORT_VERSION,
    PUBLICATIONS,
    _known_departments,
    extract_department_context_pdf,
)
from src.storage.database import get_session_factory
from src.storage.models import (
    InclusionIndicator,
    InclusionObservation,
    InclusionSourceDocument,
)

HARMONIZATION_VERSION = "risk-score-historical-harmonization-v1"


@dataclass(slots=True)
class HistoricalHarmonizationReport:
    years: list[int]
    departments_by_year: dict[int, int]
    observations_inserted: int = 0
    observations_unchanged: int = 0


def harmonize_historical_departments(
    years: tuple[int, ...] = (2023, 2024),
    *,
    dry_run: bool = False,
) -> HistoricalHarmonizationReport:
    unsupported = sorted(set(years).difference(PUBLICATIONS))
    if unsupported:
        raise ValueError(f"Unsupported publication years: {unsupported}")
    report = HistoricalHarmonizationReport(
        years=list(years), departments_by_year={}
    )
    factory = get_session_factory()
    with factory() as session:
        known = _known_departments(session)
        indicators = {
            row.code: row
            for row in session.execute(select(InclusionIndicator)).scalars()
        }
        revenue_by_department = _latest_department_values(
            session, indicators["revenu_median"].id
        )
        for year in years:
            publication = PUBLICATIONS[year]
            if publication["format"] != "pdf":
                raise ValueError(f"No verified historical PDF parser for {year}")
            response = requests.get(publication["document_url"], timeout=60)
            response.raise_for_status()
            context = extract_department_context_pdf(response.content, known)
            report.departments_by_year[year] = len(context)
            if len(context) != len(known):
                raise ValueError(
                    f"Incomplete context for {year}: {len(context)}/{len(known)}"
                )
            document = _source_document(
                session, year, publication, response.content
            )
            for code, values in context.items():
                payloads = {
                    "taux_chomage": (
                        float(values["taux_chomage"]),
                        "%",
                        f"Banque de France context; source_year={year}",
                    ),
                    "taux_pauvrete": (
                        float(values["taux_pauvrete"]),
                        "%",
                        f"Banque de France/INSEE context; source_year={year - 2}",
                    ),
                }
                revenue = revenue_by_department.get(code)
                if revenue:
                    payloads["revenu_median"] = (
                        revenue[0],
                        "euros",
                        revenue[1],
                    )
                for indicator_code, (value, unit, source_note) in payloads.items():
                    key = hashlib.sha256(
                        f"{HARMONIZATION_VERSION}|{year}|{code}|"
                        f"{indicator_code}|{value}".encode()
                    ).hexdigest()
                    exists = session.execute(
                        select(InclusionObservation.id).where(
                            InclusionObservation.idempotence_key == key
                        )
                    ).scalar_one_or_none()
                    if exists:
                        report.observations_unchanged += 1
                        continue
                    indicator = indicators[indicator_code]
                    session.add(
                        InclusionObservation(
                            source_document_id=document.id,
                            indicator_id=indicator.id,
                            idempotence_key=key,
                            indicator_code=indicator_code,
                            region_code="FR",
                            reference_period=str(year),
                            geographic_level="department",
                            geographic_code=code,
                            geographic_name=str(values["geographic_name"]),
                            value_numeric=value,
                            unit=unit,
                            observation_type="annual",
                            source_label=indicator.label,
                            source_fragment=(
                                f"{source_note}; harmonization="
                                f"{HARMONIZATION_VERSION}"
                            ),
                            extraction_method=HARMONIZATION_VERSION,
                            confidence_score=1.0,
                        )
                    )
                    report.observations_inserted += 1
        if dry_run:
            session.rollback()
        else:
            session.commit()
    return report


def _latest_department_values(session, indicator_id):
    rows = session.execute(
        select(InclusionObservation)
        .where(
            InclusionObservation.geographic_level == "department",
            InclusionObservation.indicator_id == indicator_id,
            InclusionObservation.value_numeric.is_not(None),
        )
        .order_by(
            InclusionObservation.geographic_code,
            InclusionObservation.reference_period.desc(),
        )
    ).scalars()
    output = {}
    for row in rows:
        code = str(row.geographic_code)
        output.setdefault(
            code,
            (
                float(row.value_numeric),
                row.source_fragment
                or "Filosofi measure; source year retained from source",
            ),
        )
    return output


def _source_document(session, year, publication, content):
    digest = hashlib.sha256(
        content + f"|{HARMONIZATION_VERSION}|{year}".encode()
    ).hexdigest()
    existing = session.execute(
        select(InclusionSourceDocument).where(
            InclusionSourceDocument.pdf_sha256 == digest
        )
    ).scalar_one_or_none()
    if existing:
        return existing
    document = InclusionSourceDocument(
        source_name="Banque de France + INSEE Filosofi",
        publication_type="historical_department_context",
        region_code="FR",
        region_name="France métropolitaine",
        reference_period=str(year),
        page_url=publication["page_url"],
        pdf_url=publication["document_url"],
        pdf_filename=publication["document_url"].rsplit("/", 1)[-1],
        pdf_sha256=digest,
        storage_path=publication["document_url"],
        extraction_status="success",
        extractor_version=HARMONIZATION_VERSION,
    )
    session.add(document)
    session.flush()
    return document


def report_as_dict(report: HistoricalHarmonizationReport) -> dict:
    return asdict(report)
