"""Import annual departmental over-indebtedness rates from Banque de France."""

from __future__ import annotations

import hashlib
import io
import re
import unicodedata
from dataclasses import asdict, dataclass
from urllib.parse import urljoin

import pandas as pd
import pdfplumber
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
PUBLICATIONS = {
    2023: {
        "page_url": (
            "https://www.banque-france.fr/fr/publications-et-statistiques/"
            "statistiques/enquete-typologique-sur-le-surendettement-des-menages-en-2023"
        ),
        "document_url": (
            "https://www.banque-france.fr/system/files/2024-02/"
            "SUREN-2023_Cahier-regional-departemental.pdf"
        ),
        "format": "pdf",
    },
    2024: {
        "page_url": (
            "https://www.banque-france.fr/fr/publications-et-statistiques/"
            "statistiques/enquete-typologique-sur-le-surendettement-des-menages-en-2024"
        ),
        "document_url": (
            "https://www.banque-france.fr/system/files/2025-02/"
            "SUREN-2024_Cahier-regional-departemental.pdf"
        ),
        "format": "pdf",
    },
    2025: {
        "page_url": PUBLICATION_URL,
        "format": "xlsx_collection",
    },
}
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
        "".join(
            " " if unicodedata.category(char).startswith("P") else char
            for char in value
            if not unicodedata.combining(char)
        )
        .lower()
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


def extract_department_rates_pdf(
    document: bytes,
    known_departments: dict[str, tuple[str, str]],
) -> dict[str, tuple[str, float]]:
    """Read department blocks column by column from the official annual booklet."""
    found: dict[str, tuple[str, float]] = {}
    for code, official_name, block in _iter_department_blocks(
        document, known_departments
    ):
        rate_match = re.search(
            r"([\d ]+)\s+depots?\s+de\s+dossiers\s+pour\s+100\s+000",
            block,
        )
        if rate_match:
            raw = rate_match.group(1).replace(" ", "")
            found[code] = (official_name, float(raw) / 100.0)
    return found


def extract_department_context_pdf(
    document: bytes,
    known_departments: dict[str, tuple[str, str]],
) -> dict[str, dict[str, float | str]]:
    """Extract annual contextual indicators published beside each department."""
    found: dict[str, dict[str, float | str]] = {}
    for code, official_name, block in _iter_department_blocks(
        document, known_departments
    ):
        unemployment = re.search(r"(\d+)\s+(\d+)\s+de\s+chomage\s+e", block)
        poverty = re.search(
            r"(\d+)(?:\s+(\d+))?\s+des\s+menages\s+sous\s+le\s+seuil\s+"
            r"de\s+pauvrete\s+h",
            block,
        )
        if unemployment and poverty:
            found[code] = {
                "geographic_name": official_name,
                "taux_chomage": _decimal_groups(unemployment),
                "taux_pauvrete": _decimal_groups(poverty),
            }
    return found


def _iter_department_blocks(document, known_departments):
    with pdfplumber.open(io.BytesIO(document)) as pdf:
        for page in pdf.pages:
            width, height = page.width, page.height
            for left, right in (
                (0, width / 2),
                (width / 2, width),
            ):
                text = page.crop((left, 0, right, height)).extract_text() or ""
                normalized_text = normalize_name(text)
                candidates = []
                for normalized_name, (code, official_name) in known_departments.items():
                    for match in re.finditer(
                        rf"(?<!\w){re.escape(normalized_name)}(?!\w)",
                        normalized_text,
                    ):
                        candidates.append(
                            (match.start(), match.end(), code, official_name)
                        )
                # Prefer compound names over a department name nested inside
                # them (e.g. Haute-Loire/Loire, Val-d'Oise/Oise).
                headers = [
                    candidate
                    for candidate in candidates
                    if not any(
                        other[0] <= candidate[0]
                        and other[1] >= candidate[1]
                        and (other[1] - other[0])
                        > (candidate[1] - candidate[0])
                        for other in candidates
                    )
                ]
                headers.sort()
                for index, (start, _end, code, official_name) in enumerate(headers):
                    end = (
                        headers[index + 1][0]
                        if index + 1 < len(headers)
                        else len(normalized_text)
                    )
                    block = normalized_text[start:end]
                    rate_match = re.search(
                        r"([\d ]+)\s+depots?\s+de\s+dossiers\s+pour\s+100\s+000",
                        block,
                    )
                    if rate_match:
                        yield code, official_name, block


def _decimal_groups(match: re.Match) -> float:
    decimal = match.group(2)
    return float(f"{match.group(1)}.{decimal}") if decimal else float(match.group(1))


def import_department_rates(*, year: int = 2025, dry_run: bool = False):
    if year not in PUBLICATIONS:
        raise ValueError(f"Unsupported publication year: {year}")
    publication = PUBLICATIONS[year]
    session_factory = get_session_factory()
    report = DepartmentRateImportReport(year=year)
    with session_factory() as session:
        known = _known_departments(session)
        indicator = session.execute(
            select(InclusionIndicator).where(
                InclusionIndicator.code
                == "dossiers_surendettement_1000_habitants"
            )
        ).scalar_one()
        monthly_periods = {
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
        periods = monthly_periods or {str(year)}
        all_rates: dict[str, tuple[str, float, str, str]] = {}
        if publication["format"] == "pdf":
            links = [publication["document_url"]]
        else:
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
                }
            )
        for link in links:
            response = requests.get(link, timeout=60)
            response.raise_for_status()
            report.workbooks += 1
            extracted = (
                extract_department_rates_pdf(response.content, known)
                if publication["format"] == "pdf"
                else extract_department_rates(response.content, known)
            )
            for code, (name, rate) in extracted.items():
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
                        observation_type=(
                            "annual_replicated_monthly"
                            if len(period) == 7
                            else "annual"
                        ),
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
        page_url=PUBLICATIONS[int(period[:4])]["page_url"],
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
