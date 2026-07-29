from src.risk_score.department_debt_import import normalize_name


def test_department_name_normalization():
    assert normalize_name("Pas-de-Calais") == "pas de calais"
    assert normalize_name("Côtes-d’Armor") == "cotes d armor"
