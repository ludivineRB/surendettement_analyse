from src.risk_score.inflation_import import parse_insee_series, year_on_year_rates


def test_parse_insee_series_and_compute_year_on_year_rate():
    payload = b"""<?xml version="1.0"?>
    <Data xmlns="urn:test"><Series>
      <Obs TIME_PERIOD="2024-01" OBS_VALUE="100.0"/>
      <Obs TIME_PERIOD="2025-01" OBS_VALUE="102.5"/>
      <Obs TIME_PERIOD="2025-02" OBS_VALUE="103.0"/>
    </Series></Data>"""
    indexes = parse_insee_series(payload)
    assert indexes == {"2024-01": 100.0, "2025-01": 102.5, "2025-02": 103.0}
    assert year_on_year_rates(indexes) == {"2025-01": 2.499999999999991}
