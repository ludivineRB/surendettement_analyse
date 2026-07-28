import csv
import io
import zipfile

import pytest
from sqlalchemy import select

from src.risk_score.filosofi_import import (
    DATA_MEMBER,
    IMPORT_VERSION,
    import_filosofi,
)
from src.risk_score.service import RiskScoreCalculator
from src.storage.models import InclusionObservation

from app.tests.test_analytics_bridge import (
    _analytics_fixture,
    _operational_factory,
)
from src.risk_score.analytics_bridge import import_analytics_indicators


def _filosofi_fixture(path):
    fields = [
        "GEO",
        "GEO_OBJECT",
        "FILOSOFI_MEASURE",
        "UNIT_MEASURE",
        "UNIT_MULT",
        "CONF_STATUS",
        "OBS_STATUS",
        "TIME_PERIOD",
        "OBS_VALUE",
    ]
    rows = []
    for geo, level, poverty, income in (
        ("01", "DEP", 10.8, 24810),
        ("03", "DEP", 16.2, 21500),
        ("84", "REG", 13.3, 23800),
        ("99", "DEP", 99, 1),
    ):
        rows.extend(
            [
                [geo, level, "PR_MD60", "PT", "0", "F", "A", 2021, poverty],
                [geo, level, "MED_SL", "EUR", "0", "F", "A", 2021, income],
            ]
        )
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\n")
    writer.writerow(fields)
    writer.writerows(rows)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(DATA_MEMBER, buffer.getvalue())


def test_filosofi_import_enables_region_score_and_stays_idempotent(tmp_path):
    analytics_path = tmp_path / "analytics.db"
    filosofi_path = tmp_path / "filosofi.zip"
    _analytics_fixture(analytics_path)
    _filosofi_fixture(filosofi_path)
    factory = _operational_factory(tmp_path / "operational.db")
    import_analytics_indicators(analytics_path, factory=factory)

    dry = import_filosofi(filosofi_path, dry_run=True, factory=factory)
    assert dry.inserted == 6
    first = import_filosofi(filosofi_path, factory=factory)
    second = import_filosofi(filosofi_path, factory=factory)
    assert first.inserted == 6
    assert first.skipped == 2
    assert second.inserted == 0
    assert second.unchanged == 6

    with factory() as session:
        rows = session.execute(
            select(InclusionObservation).where(
                InclusionObservation.extraction_method == IMPORT_VERSION
            )
        ).scalars().all()
        assert len(rows) == 6
        assert {row.reference_period for row in rows} == {"2025-06"}
        assert all("annual_source_year=2021" in row.source_fragment for row in rows)
        assert next(
            row for row in rows
            if row.geographic_level == "region"
            and row.indicator_code == "taux_pauvrete"
        ).value_numeric == pytest.approx(13.3)

    region = RiskScoreCalculator(factory).calculate(
        "region", "2025-06", dry_run=True
    )
    departments = RiskScoreCalculator(factory).calculate(
        "department", "2025-06", dry_run=True
    )
    assert region.results[0].coverage_ratio == pytest.approx(0.85)
    assert region.results[0].status == "partial"
    assert region.results[0].score is not None
    assert all(item.coverage_ratio == pytest.approx(0.55) for item in departments.results)
    assert all(item.status == "insufficient_data" for item in departments.results)
