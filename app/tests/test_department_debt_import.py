import pytest

from src.risk_score.department_debt_import import (
    import_department_rates,
    normalize_name,
)


def test_department_name_normalization():
    assert normalize_name("Pas-de-Calais") == "pas de calais"
    assert normalize_name("Côtes-d’Armor") == "cotes d armor"


def test_department_import_rejects_unverified_year():
    with pytest.raises(ValueError, match="Unsupported publication year"):
        import_department_rates(year=2021, dry_run=True)
