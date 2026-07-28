"""Idempotent import of usable legacy ``surendettement_data`` rows."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from src.storage.database import get_session_factory
from src.storage.models import (
    InclusionIndicator,
    InclusionObservation,
    InclusionSourceDocument,
    SurendettementData,
)


@dataclass(slots=True)
class LegacyImportReport:
    examined: int = 0
    imported: int = 0
    duplicates: int = 0
    non_importable: list[str] = field(default_factory=list)


def import_legacy_surendettement(
    factory: sessionmaker | None = None,
    dry_run: bool = False,
) -> LegacyImportReport:
    """Import only rows with an explicit department code and finite value."""
    factory = factory or get_session_factory()
    report = LegacyImportReport()
    with factory() as session:
        rows = session.execute(select(SurendettementData).order_by(SurendettementData.id)).scalars()
        for row in rows:
            report.examined += 1
            geographic_code = _department_code(row.region)
            if geographic_code is None or row.year is None or row.value is None:
                report.non_importable.append(f"id={row.id}:missing_geography_period_or_value")
                continue
            value = float(row.value)
            if not math.isfinite(value):
                report.non_importable.append(f"id={row.id}:non_finite_value")
                continue
            indicator_code = f"legacy_{_slugify(row.indicator)}"
            idempotence_key = _stable_hash(
                f"legacy|{row.id}|{row.year}|{geographic_code}|"
                f"{indicator_code}|{value}|{row.source_file}"
            )
            if session.execute(
                select(InclusionObservation.id).where(
                    InclusionObservation.idempotence_key == idempotence_key
                )
            ).scalar_one_or_none():
                report.duplicates += 1
                continue
            if dry_run:
                report.imported += 1
                continue

            indicator = session.execute(
                select(InclusionIndicator).where(InclusionIndicator.code == indicator_code)
            ).scalar_one_or_none()
            if indicator is None:
                indicator = InclusionIndicator(
                    code=indicator_code,
                    label=str(row.indicator),
                    category="legacy_surendettement",
                    default_unit="unknown",
                )
                session.add(indicator)
                session.flush()

            source_hash = _stable_hash(f"legacy-source|{row.source_file}")
            document = session.execute(
                select(InclusionSourceDocument).where(
                    InclusionSourceDocument.pdf_sha256 == source_hash
                )
            ).scalar_one_or_none()
            if document is None:
                document = InclusionSourceDocument(
                    source_name="Legacy surendettement_data",
                    publication_type="legacy_import",
                    region_code="legacy",
                    region_name="Import historique",
                    reference_period=str(row.year),
                    page_url=f"legacy://{row.source_file}",
                    pdf_url=f"legacy://{row.source_file}",
                    pdf_filename=str(row.source_file),
                    pdf_sha256=source_hash,
                    storage_path=str(row.source_file),
                    extraction_status="success",
                    extractor_version="legacy-import-v1",
                )
                session.add(document)
                session.flush()

            session.add(
                InclusionObservation(
                    source_document_id=document.id,
                    indicator_id=indicator.id,
                    idempotence_key=idempotence_key,
                    indicator_code=indicator.code,
                    region_code="",
                    reference_period=str(row.year),
                    geographic_level="department",
                    geographic_code=geographic_code,
                    geographic_name=str(row.region),
                    value_numeric=value,
                    unit="unknown",
                    observation_type="annual",
                    source_label=str(row.indicator),
                    source_fragment=f"legacy:{row.source_file}",
                    extraction_method="legacy_import",
                    confidence_score=0.5,
                )
            )
            report.imported += 1
        if not dry_run:
            session.commit()
    return report


def _department_code(value: object) -> str | None:
    text = str(value or "").strip().upper().replace(".0", "")
    if text in {"2A", "2B"}:
        return text
    if re.fullmatch(r"\d{1,2}", text):
        return text.zfill(2)
    return None


def _slugify(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_") or "unknown"


def _stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
