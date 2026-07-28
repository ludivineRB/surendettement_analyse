"""SQLAlchemy ORM models for pipeline storage."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
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
    __table_args__ = (
        UniqueConstraint("idempotence_key", name="uq_observations_idempotence_key"),
        Index(
            "ix_observations_geo_period_indicator",
            "geographic_level",
            "reference_period",
            "indicator_id",
            "geographic_code",
        ),
        Index(
            "ix_observations_code_level_period",
            "indicator_code",
            "geographic_level",
            "reference_period",
        ),
    )

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


class RiskScoreModel(Base):
    __tablename__ = "risk_score_models"
    __table_args__ = (
        UniqueConstraint("code", "version", name="uq_risk_score_models_code_version"),
        CheckConstraint(
            "minimum_coverage_ratio >= 0 AND minimum_coverage_ratio <= 1",
            name="ck_risk_score_models_coverage",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalization_method: Mapped[str] = mapped_column(String(64), nullable=False, default="min_max")
    minimum_coverage_ratio: Mapped[float] = mapped_column(Numeric(8, 6), nullable=False, default=0.6)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    configuration_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[str] = mapped_column(String(32), default=utc_now)
    updated_at: Mapped[str] = mapped_column(String(32), default=utc_now, onupdate=utc_now)


class RiskScoreIndicatorConfig(Base):
    __tablename__ = "risk_score_indicator_configs"
    __table_args__ = (
        UniqueConstraint(
            "risk_score_model_id",
            "indicator_code",
            name="uq_risk_score_indicator_model_code",
        ),
        CheckConstraint("weight > 0", name="ck_risk_score_indicator_weight"),
        CheckConstraint(
            "direction IN ('positive', 'negative')",
            name="ck_risk_score_indicator_direction",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    risk_score_model_id: Mapped[int] = mapped_column(
        ForeignKey("risk_score_models.id"),
        nullable=False,
        index=True,
    )
    indicator_id: Mapped[int | None] = mapped_column(
        ForeignKey("indicators.id"),
        nullable=True,
        index=True,
    )
    indicator_code: Mapped[str] = mapped_column(String(128), nullable=False)
    logical_code: Mapped[str] = mapped_column(String(128), nullable=False)
    weight: Mapped[float] = mapped_column(Numeric(12, 8), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    normalization_method: Mapped[str] = mapped_column(String(64), nullable=False, default="min_max")
    fixed_min: Mapped[float | None] = mapped_column(Numeric(20, 8), nullable=True)
    fixed_max: Mapped[float | None] = mapped_column(Numeric(20, 8), nullable=True)
    expected_unit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[str] = mapped_column(String(32), default=utc_now)
    updated_at: Mapped[str] = mapped_column(String(32), default=utc_now, onupdate=utc_now)


class RiskScore(Base):
    __tablename__ = "risk_scores"
    __table_args__ = (
        UniqueConstraint(
            "risk_score_model_id",
            "geographic_level",
            "geographic_code",
            "reference_period",
            name="uq_risk_scores_business_key",
        ),
        CheckConstraint("score IS NULL OR (score >= 0 AND score <= 100)", name="ck_risk_scores_score"),
        CheckConstraint(
            "coverage_ratio >= 0 AND coverage_ratio <= 1",
            name="ck_risk_scores_coverage",
        ),
        CheckConstraint(
            "status IN ('valid', 'partial', 'insufficient_data', 'error')",
            name="ck_risk_scores_status",
        ),
        Index(
            "ix_risk_scores_model_level_period_score",
            "risk_score_model_id",
            "geographic_level",
            "reference_period",
            "score",
        ),
        Index(
            "ix_risk_scores_geo_period",
            "geographic_level",
            "geographic_code",
            "reference_period",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    risk_score_model_id: Mapped[int] = mapped_column(
        ForeignKey("risk_score_models.id"),
        nullable=False,
        index=True,
    )
    geographic_level: Mapped[str] = mapped_column(String(32), nullable=False)
    geographic_code: Mapped[str] = mapped_column(String(64), nullable=False)
    geographic_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reference_period: Mapped[str] = mapped_column(String(16), nullable=False)
    score: Mapped[float | None] = mapped_column(Numeric(12, 8), nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    coverage_ratio: Mapped[float] = mapped_column(Numeric(8, 6), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    missing_indicators_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    warnings_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    calculated_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now)
    created_at: Mapped[str] = mapped_column(String(32), default=utc_now)
    updated_at: Mapped[str] = mapped_column(String(32), default=utc_now, onupdate=utc_now)


class RiskScoreDetail(Base):
    __tablename__ = "risk_score_details"
    __table_args__ = (
        UniqueConstraint("risk_score_id", "indicator_code", name="uq_risk_score_details_score_code"),
        CheckConstraint(
            "normalized_value >= 0 AND normalized_value <= 1",
            name="ck_risk_score_details_normalized",
        ),
        CheckConstraint("configured_weight > 0", name="ck_risk_score_details_configured_weight"),
        CheckConstraint("effective_weight > 0", name="ck_risk_score_details_effective_weight"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    risk_score_id: Mapped[int] = mapped_column(
        ForeignKey("risk_scores.id"),
        nullable=False,
        index=True,
    )
    indicator_id: Mapped[int | None] = mapped_column(ForeignKey("indicators.id"), nullable=True)
    indicator_code: Mapped[str] = mapped_column(String(128), nullable=False)
    raw_value: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    population_min: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    population_max: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    normalized_value: Mapped[float] = mapped_column(Numeric(12, 8), nullable=False)
    configured_weight: Mapped[float] = mapped_column(Numeric(12, 8), nullable=False)
    effective_weight: Mapped[float] = mapped_column(Numeric(12, 8), nullable=False)
    contribution: Mapped[float] = mapped_column(Numeric(12, 8), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    source_observation_id: Mapped[int | None] = mapped_column(
        ForeignKey("observations.id"),
        nullable=True,
    )
    created_at: Mapped[str] = mapped_column(String(32), default=utc_now)
    updated_at: Mapped[str] = mapped_column(String(32), default=utc_now, onupdate=utc_now)
