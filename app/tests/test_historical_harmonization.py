import pytest

from src.risk_score.historical_harmonization import (
    harmonize_historical_departments,
)


def test_historical_harmonization_rejects_unknown_year():
    with pytest.raises(ValueError, match="Unsupported publication years"):
        harmonize_historical_departments((2020,), dry_run=True)
