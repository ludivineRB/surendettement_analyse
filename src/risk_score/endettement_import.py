"""Import mean global debt per treated case from official BDF workbooks."""

from __future__ import annotations

import hashlib
import io
from dataclasses import asdict, dataclass
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup
from sqlalchemy import select

from src.risk_score.department_debt_import import (
    PUBLICATIONS,
    _known_departments,
    normalize_name,
)
from src.storage.database import get_session_factory
from src.storage.models import (
    InclusionIndicator,
    InclusionObservation,
    InclusionSourceDocument,
    RiskScoreIndicatorConfig,
    RiskScoreModel,
)

IMPORT_VERSION = "risk-score-bdf-mean-debt-v1"
SHEET_NAME_ALIASES = {
    # Typo present in the official 2024 workbook.
    "indre et loir": "indre et loire",
}


@dataclass(slots=True)
class MeanDebtImportReport:
    years: list[int]
    departments_by_year: dict[int, int]
    observations_inserted: int = 0
    observations_unchanged: int = 0
    model_mapped: bool = False


def extract_mean_debt(
    workbook: bytes,
    known_departments: dict[str, tuple[str, str]],
) -> dict[str, tuple[str, float]]:
    result = {}
    excel = pd.ExcelFile(io.BytesIO(workbook))
    for sheet in excel.sheet_names:
        normalized_sheet = normalize_name(sheet)
        normalized_sheet = SHEET_NAME_ALIASES.get(
            normalized_sheet, normalized_sheet
        )
        department = known_departments.get(normalized_sheet)
        if not department:
            continue
        data = pd.read_excel(excel, sheet_name=sheet, header=None)
        for _, row in data.iterrows():
            values = [value for value in row.tolist() if pd.notna(value)]
            if not values or normalize_name(str(values[0])) != "endettement global":
                continue
            if len(values) < 3:
                continue
            encours_thousand_euros = float(values[1])
            treated_cases = float(values[2])
            if encours_thousand_euros <= 0 or treated_cases <= 0:
                continue
            code, name = department
            result[code] = (
                name,
                encours_thousand_euros * 1000.0 / treated_cases,
            )
    return result


def import_mean_debt(
    years: tuple[int, ...] = (2023, 2024, 2025),
    *,
    dry_run: bool = False,
) -> MeanDebtImportReport:
    unsupported = sorted(set(years).difference(PUBLICATIONS))
    if unsupported:
        raise ValueError(f"Unsupported publication years: {unsupported}")
    report = MeanDebtImportReport(years=list(years), departments_by_year={})
    factory = get_session_factory()
    with factory() as session:
        known = _known_departments(session)
        indicator = session.execute(
            select(InclusionIndicator).where(
                InclusionIndicator.code == "endettement_moyen"
            )
        ).scalar_one_or_none()
        if indicator is None:
            indicator = InclusionIndicator(
                code="endettement_moyen",
                label="Endettement global moyen par dossier traité",
                category="surendettement",
                description=(
                    "Encours global des dettes en milliers d'euros multiplié "
                    "par 1 000 et divisé par le nombre de dossiers traités."
                ),
                default_unit="euros",
            )
            session.add(indicator)
            session.flush()
        for year in years:
            publication = PUBLICATIONS[year]
            page = requests.get(publication["page_url"], timeout=60)
            page.raise_for_status()
            soup = BeautifulSoup(page.text, "html.parser")
            links = sorted(
                {
                    urljoin(publication["page_url"], anchor["href"])
                    for anchor in soup.select("a[href]")
                    if anchor["href"].lower().endswith(".xlsx")
                    and "comparaison" not in anchor["href"].lower()
                    and "national" not in anchor["href"].lower()
                    and "_dom" not in anchor["href"].lower()
                }
            )
            extracted = {}
            sources = {}
            for link in links:
                response = requests.get(link, timeout=60)
                response.raise_for_status()
                digest = hashlib.sha256(response.content).hexdigest()
                for code, payload in extract_mean_debt(
                    response.content, known
                ).items():
                    extracted[code] = payload
                    sources[code] = (link, digest)
            report.departments_by_year[year] = len(extracted)
            if len(extracted) != len(known):
                raise ValueError(
                    f"Incomplete mean debt for {year}: "
                    f"{len(extracted)}/{len(known)}"
                )
            monthly_periods = {
                period
                for period in session.execute(
                    select(InclusionObservation.reference_period)
                    .where(
                        InclusionObservation.geographic_level == "department",
                        InclusionObservation.reference_period.like(f"{year}-%"),
                    )
                    .distinct()
                ).scalars()
            }
            periods = monthly_periods or {str(year)}
            for code, (name, value) in extracted.items():
                link, source_hash = sources[code]
                for period in periods:
                    document = _source_document(
                        session, year, period, link, source_hash
                    )
                    key = hashlib.sha256(
                        f"{IMPORT_VERSION}|{period}|{code}|{value}".encode()
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
                            indicator_code=indicator.code,
                            region_code="FR",
                            reference_period=period,
                            geographic_level="department",
                            geographic_code=code,
                            geographic_name=name,
                            value_numeric=value,
                            unit="euros",
                            observation_type=(
                                "annual_replicated_monthly"
                                if len(period) == 7
                                else "annual"
                            ),
                            source_label=indicator.label,
                            source_fragment=(
                                "formula=global_debt_thousand_euros*1000/"
                                f"treated_cases; source_year={year}"
                            ),
                            extraction_method=IMPORT_VERSION,
                            confidence_score=1.0,
                        )
                    )
                    report.observations_inserted += 1
        for config in session.execute(
            select(RiskScoreIndicatorConfig)
            .join(
                RiskScoreModel,
                RiskScoreModel.id
                == RiskScoreIndicatorConfig.risk_score_model_id,
            )
            .where(
                RiskScoreModel.code == "default",
                RiskScoreIndicatorConfig.logical_code == "endettement_moyen",
            )
        ).scalars():
            config.indicator_id = indicator.id
            config.indicator_code = indicator.code
            report.model_mapped = True
        if dry_run:
            session.rollback()
        else:
            session.commit()
    return report


def _source_document(session, year, period, link, source_hash):
    digest = hashlib.sha256(
        f"{source_hash}|{IMPORT_VERSION}|{period}".encode()
    ).hexdigest()
    existing = session.execute(
        select(InclusionSourceDocument).where(
            InclusionSourceDocument.pdf_sha256 == digest
        )
    ).scalar_one_or_none()
    if existing:
        return existing
    publication = PUBLICATIONS[year]
    document = InclusionSourceDocument(
        source_name="Banque de France",
        publication_type="department_mean_global_debt",
        region_code="FR",
        region_name="France métropolitaine",
        reference_period=period,
        page_url=publication["page_url"],
        pdf_url=link,
        pdf_filename=link.rsplit("/", 1)[-1],
        pdf_sha256=digest,
        storage_path=link,
        extraction_status="success",
        extractor_version=IMPORT_VERSION,
    )
    session.add(document)
    session.flush()
    return document


def report_as_dict(report: MeanDebtImportReport) -> dict:
    return asdict(report)
