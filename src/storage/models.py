"""SQLAlchemy ORM models for pipeline storage."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SurendettementData(Base):
    __tablename__ = "surendettement_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    region: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    indicator: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_file: Mapped[str] = mapped_column(String(255), nullable=False)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class InclusionSourceDocument(Base):
    __tablename__ = "source_documents"
    __table_args__ = (
        UniqueConstraint("pdf_sha256", name="uq_source_documents_pdf_sha256"),
        UniqueConstraint(
            "publication_type",
            "region_code",
            "reference_period",
            "pdf_sha256",
            name="uq_source_documents_business_version",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    publication_type: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    region_code: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    region_name: Mapped[str] = mapped_column(String(255), nullable=False)
    reference_period: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    publication_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    updated_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    page_url: Mapped[str] = mapped_column(Text, nullable=False)
    pdf_url: Mapped[str] = mapped_column(Text, nullable=False)
    pdf_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    pdf_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    pdf_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    http_etag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    http_last_modified: Mapped[str | None] = mapped_column(String(255), nullable=True)
    downloaded_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    extraction_status: Mapped[str] = mapped_column(String(64), nullable=False, default="pending")
    extractor_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), default=utc_now)
    updated_at: Mapped[str] = mapped_column(String(32), default=utc_now, onupdate=utc_now)


class InclusionIndicator(Base):
    __tablename__ = "indicators"
    __table_args__ = (UniqueConstraint("code", name="uq_indicators_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(512), nullable=False)
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_unit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[str] = mapped_column(String(32), default=utc_now)
    updated_at: Mapped[str] = mapped_column(String(32), default=utc_now, onupdate=utc_now)


class InclusionObservation(Base):
    __tablename__ = "observations"
    __table_args__ = (UniqueConstraint("idempotence_key", name="uq_observations_idempotence_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_document_id: Mapped[int] = mapped_column(ForeignKey("source_documents.id"), nullable=False, index=True)
    indicator_id: Mapped[int] = mapped_column(ForeignKey("indicators.id"), nullable=False, index=True)
    idempotence_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    indicator_code: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    region_code: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    reference_period: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    geographic_level: Mapped[str] = mapped_column(String(64), nullable=False)
    geographic_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    geographic_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    value_numeric: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    observation_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    comparison_period: Mapped[str | None] = mapped_column(String(32), nullable=True)
    variation_numeric: Mapped[float | None] = mapped_column(Float, nullable=True)
    variation_unit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_label: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_fragment: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_method: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[str] = mapped_column(String(32), default=utc_now)
    updated_at: Mapped[str] = mapped_column(String(32), default=utc_now, onupdate=utc_now)
