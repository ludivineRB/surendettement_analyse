"""Pydantic schemas for analytical data API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DepartmentRead(BaseModel):
    """Territorial reference exposed by the analytical API."""

    departement_code: str
    departement_name: str
    region_name: str | None = None
    is_metropolitan_scope: bool


class IndicatorRead(BaseModel):
    """Indicator available in the PostgreSQL analytical model."""

    indicator_key: str
    source_system: str
    indicator_code: str
    indicator_name: str
    indicator_group: str | None = None
    unit: str | None = None
    aggregation_rule: str | None = None


class SurendettementObservationRead(BaseModel):
    """Annual over-indebtedness observation by department and indicator."""

    reference_year: int
    departement_code: str
    departement_name: str | None = None
    region_name: str | None = None
    indicator_code: str
    indicator_name: str
    indicator_group: str | None = None
    unit: str | None = None
    value: float
    surendettement_value: float
    dossiers_deposes: float
    source_file: str | None = None


class MacroOverrideCreate(BaseModel):
    reference_year: int = Field(ge=1900, le=2100)
    departement_code: str = Field(min_length=2, max_length=3)
    indicator_code: str = Field(min_length=1, max_length=255)
    indicator_name: str | None = None
    indicator_group: str | None = None
    value: float
    source_note: str | None = None


class MacroOverrideUpdate(BaseModel):
    indicator_name: str | None = None
    indicator_group: str | None = None
    value: float | None = None
    source_note: str | None = None


class MacroOverrideRead(MacroOverrideCreate):
    id: int
    created_at: str
    updated_at: str
