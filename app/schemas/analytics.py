"""Pydantic schemas for analytical data API."""

from __future__ import annotations

from pydantic import BaseModel, Field


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
