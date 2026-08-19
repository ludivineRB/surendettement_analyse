"""Validated contract for deterministic analytical questions."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


IntentName = Literal[
    "get_score",
    "get_score_factors",
    "get_time_series",
    "compare_periods",
    "compare_models",
    "rank_territories",
    "find_largest_increase",
    "get_data_freshness",
    "get_pipeline_status",
]


class AnalyticalIntent(BaseModel):
    """Allow-listed analytical operation; never contains free-form SQL."""

    model_config = ConfigDict(extra="forbid")

    intent: IntentName
    geographic_level: Literal["department", "region"] | None = None
    geographic_code: str | None = Field(default=None, max_length=10)
    metric: Literal["risk_score"] = "risk_score"
    model_version: str | None = Field(default=None, pattern=r"^\d+\.\d+\.\d+$")
    comparison_model_version: str | None = Field(
        default=None,
        pattern=r"^\d+\.\d+\.\d+$",
    )
    period_start: str | None = Field(
        default=None,
        pattern=r"^\d{4}(?:-(?:0[1-9]|1[0-2]))?$",
    )
    period_end: str | None = Field(
        default=None,
        pattern=r"^\d{4}(?:-(?:0[1-9]|1[0-2]))?$",
    )
    order: Literal["ascending", "descending"] = "descending"
    limit: int = Field(default=10, ge=1, le=100)

    @model_validator(mode="after")
    def validate_intent_requirements(self):
        territory_intents = {
            "get_score",
            "get_score_factors",
            "get_time_series",
            "compare_periods",
        }
        if self.intent in territory_intents and not (
            self.geographic_level and self.geographic_code
        ):
            raise ValueError("Cette intention exige un territoire.")
        if self.intent in {"get_score", "get_score_factors"} and not self.period_start:
            raise ValueError("Cette intention exige une période.")
        if self.intent == "compare_periods" and not (
            self.period_start and self.period_end
        ):
            raise ValueError("La comparaison exige deux périodes.")
        if self.intent == "compare_models" and not (
            self.model_version and self.comparison_model_version
        ):
            raise ValueError("La comparaison exige deux versions de modèle.")
        if self.intent == "rank_territories" and not (
            self.geographic_level and self.period_start
        ):
            raise ValueError("Le classement exige un niveau et une période.")
        if self.intent == "find_largest_increase" and not (
            self.geographic_level and self.period_start and self.period_end
        ):
            raise ValueError("La hausse exige un niveau et deux périodes.")
        return self
