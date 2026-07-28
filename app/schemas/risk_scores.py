"""Pydantic contracts for territorial risk scoring."""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class RiskScoreCalculateRequest(BaseModel):
    geographic_level: str
    reference_period: str | None = None
    model_code: str = "default"
    geographic_code: str | None = None
    all_periods: bool = False
    dry_run: bool = False

    @model_validator(mode="after")
    def validate_period(self):
        if not self.all_periods and not self.reference_period:
            raise ValueError("reference_period is required unless all_periods is true")
        return self


class RiskScoreListParams(BaseModel):
    geographic_level: str | None = None
    geographic_code: str | None = None
    reference_period: str | None = None
    model_code: str | None = None
    risk_level: str | None = None
    limit: int = Field(default=100, ge=1, le=5000)
    offset: int = Field(default=0, ge=0)
