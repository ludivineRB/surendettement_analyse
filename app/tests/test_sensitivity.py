import pytest

from src.risk_score.sensitivity import (
    WEIGHT_SCENARIOS,
    _fixed_reference_score,
    validate_weight_scenarios,
)


def test_weight_scenarios_are_complete_and_sum_to_one():
    validate_weight_scenarios()
    invalid = {**WEIGHT_SCENARIOS, "bad": {**WEIGHT_SCENARIOS["baseline"]}}
    invalid["bad"]["inflation"] = 0.10
    with pytest.raises(ValueError, match="do not sum"):
        validate_weight_scenarios(invalid)


def test_fixed_reference_score_renormalizes_available_weights():
    class Config:
        def __init__(self, logical_code, direction):
            self.logical_code = logical_code
            self.direction = direction

    configs = {
        "a": Config("a", "positive"),
        "b": Config("b", "negative"),
    }
    bounds = {
        "a": {"fixed_min": 0, "fixed_max": 10},
        "b": {"fixed_min": 0, "fixed_max": 10},
    }
    weights = {"a": 0.6, "b": 0.4}
    assert _fixed_reference_score(
        {"a": 10, "b": 0}, configs, bounds, weights
    ) == pytest.approx(100)
