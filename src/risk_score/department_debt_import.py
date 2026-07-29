"""Import annual departmental over-indebtedness rates from Banque de France."""

from __future__ import annotations

import hashlib
import io
import re
import unicodedata
from dataclasses import asdict, dataclass
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup
from sqlalchemy import select

from src.storage.database import get_session_factory
from src.storage.models import (
    InclusionIndicator,
    InclusionObservation,
    InclusionSourceDocument,
)

IMPORT_VERSION = "risk-score-bdf-department-rates-v1"
PUBLICATION_URL = (
    "https://www.banque-france.fr/fr/publications-et-statistiques/publications/"
    "typologie-du-surendettement-des-menages-2025"
)
RATE_PATTERN = re.compile(
    r"([\d \u00a0]+)\s+d[ée]p[oô]ts?\s+de\s+dossiers\s+pour\s+100[ \u00a0]000",
    re.I,
)


@dataclass(slots=True)
class DepartmentRateImportReport:
    year: int
    workbooks: int = 0
    departments_found: int = 0
    observations_inserted: int = 0
    observations_unchanged: int = 0


def normalize_name(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    return " ".join(
        "".join(char for char in value if not unicodedata.combining(char))
        .lower()
        .replace("-", " ")
        .replace("’", " ")
        .replace("'", " ")
        .split()
    )


def extract_department_rates(
    workbook: bytes,
    known_departments: dict[str, tuple[str, str]],
) -> dict[str, tuple[str, float]]:
    data = pd.read_excel(
        io.BytesIO(workbook),
        sheet_name="INDICATEURS-RÉGION-DÉPTS",
        header=None,
    )
    found: dict[str, tuple[str, float]] = {}
    for row in range(len(data)):
        for column in range(len(data.columns)):
            value = data.iat[row, column]
            match = RATE_PATTERN.search(str(value))
            if not match:
                continue
            department = _nearest_department(
                data, row, column, known_departments
            )
            if department:
                code, name = department
                raw_rate = float(match.group(1).replace(" ", "").replace("\u00a0", ""))
                found[code] = (name, raw_rate / 100.0)
    return found


def import_department_rates(*, year: int = 2025, dry_run: bool = False):
    if year != 2025:
        raise ValueError("Only the verified 2025 publication is currently supported")
    session_factory = get_session_factory()
    report = DepartmentRateImportReport(year=year)
    page = requests.get(PUBLICATION_URL, timeout=60)
    page.raise_for_status()
    soup = BeautifulSoup(page.text, "html.parser")
    links = sorted(
        {
            urljoin(PUBLICATION_URL, anchor["href"])
            for anchor in soup.select("a[href]")
            if anchor["href"].lower().endswith(".xlsx")
            and "comparaison" not in anchor["href"].lower()
            and "national" not in anchor["href"].lower()
        }
    )
    with session_factory() as session:
        known = _known_departments(session)
        indicator = session.execute(
            select(InclusionIndicator).where(
                InclusionIndicator.code
                == "dossiers_surendettement_1000_habitants"
            )
        ).scalar_one()
        periods = {
            row[0]
            for row in session.execute(
                select(InclusionObservation.reference_period)
                .where(
                    InclusionObservation.geographic_level == "department",
                    InclusionObservation.reference_period.like(f"{year}-%"),
                )
                .distinct()
            )
        }
        all_rates: dict[str, tuple[str, float, str, str]] = {}
        for link in links:
            response = requests.get(link, timeout=60)
            response.raise_for_status()
            report.workbooks += 1
            for code, (name, rate) in extract_department_rates(
                response.content, known
            ).items():
                all_rates[code] = (
                    name,
                    rate,
                    link,
                    hashlib.sha256(response.content).hexdigest(),
                )
        report.departments_found = len(all_rates)
        for code, (name, rate, link, source_hash) in all_rates.items():
            for period in periods:
                document = _source_document(
                    session, period, link, source_hash, code, name
                )
                key = hashlib.sha256(
                    f"{IMPORT_VERSION}|{code}|{period}|{rate}".encode()
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
                        value_numeric=rate,
                        unit="dossiers_pour_1000_habitants",
                        observation_type="annual_replicated_monthly",
                        source_label="Dépôts pour 100 000 habitants de 15 ans et plus",
                        source_fragment=(
                            f"annual_source_year={year}; conversion=rate_per_100000/100"
                        ),
                        extraction_method=IMPORT_VERSION,
                        confidence_score=1.0,
                    )
                )
                report.observations_inserted += 1
        if dry_run:
            session.rollback()
        else:
            session.commit()
    return report


def _known_departments(session) -> dict[str, tuple[str, str]]:
    rows = session.execute(
        select(
            InclusionObservation.geographic_code,
            InclusionObservation.geographic_name,
        )
        .where(InclusionObservation.geographic_level == "department")
        .distinct()
    )
    return {
        normalize_name(name): (str(code), str(name))
        for code, name in rows
        if code and name
    }


def _nearest_department(data, row, column, known):
    for candidate_row in range(row - 1, max(-1, row - 8), -1):
        for candidate_column in range(max(0, column - 1), min(len(data.columns), column + 3)):
            candidate = normalize_name(str(data.iat[candidate_row, candidate_column]))
            if candidate in known:
                return known[candidate]
    return None


def _source_document(session, period, link, source_hash, code, name):
    digest = hashlib.sha256(
        f"{source_hash}|{IMPORT_VERSION}|{code}|{period}".encode()
    ).hexdigest()
    existing = session.execute(
        select(InclusionSourceDocument).where(
            InclusionSourceDocument.pdf_sha256 == digest
        )
    ).scalar_one_or_none()
    if existing:
        return existing
    document = InclusionSourceDocument(
        source_name="Banque de France",
        publication_type="typologie_surendettement_department",
        region_code="FR",
        region_name=name,
        reference_period=period,
        page_url=PUBLICATION_URL,
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


def report_as_dict(report: DepartmentRateImportReport) -> dict:
    return asdict(report)
