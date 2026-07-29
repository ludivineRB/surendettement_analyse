import sqlite3

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.schemas.analytics import MacroOverrideCreate
from app.tests.test_analytics_bridge import _operational_factory
from app.tests.views.test_analytics_api import _create_test_analytics_db
from app.views.analytics_api import (
    create_macro_override,
    list_regional_macro_economic_data,
)
from src.storage.conformed_dimensions import migrate_conformed_dimensions
from src.storage.models import InclusionIndicator, InclusionObservation


def test_conformed_dimension_migration_and_integrity(tmp_path):
    analytics_path = tmp_path / "analytics.db"
    operational_path = tmp_path / "operational.db"
    _create_test_analytics_db(analytics_path)
    factory = _operational_factory(operational_path)

    first = migrate_conformed_dimensions(analytics_path, operational_path)
    second = migrate_conformed_dimensions(analytics_path, operational_path)
    assert first.analytics_regions == second.analytics_regions == 13
    assert first.operational_regions == second.operational_regions == 13
    assert first.indicator_mismatches == 0
    assert first.deprecated_objects == 3

    with sqlite3.connect(analytics_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute(
            "SELECT region_code FROM dim_department WHERE departement_code='75'"
        ).fetchone() == ("11",)
        foreign_tables = {
            row[2]
            for row in connection.execute(
                "PRAGMA foreign_key_list(fact_macro_override)"
            )
        }
        assert foreign_tables == {
            "dim_period",
            "dim_department",
            "dim_indicator",
        }

    original_path = settings.ANALYTICS_DB_PATH
    settings.ANALYTICS_DB_PATH = str(analytics_path)
    try:
        rows = list_regional_macro_economic_data(
            region_code="11",
            indicator_code="P22_POP",
            reference_year=2026,
            limit=500,
            offset=0,
        )
        assert rows[0]["region_name"] == "Île-de-France"
        created = create_macro_override(
            MacroOverrideCreate(
                reference_year=2026,
                departement_code="75",
                indicator_code="custom_conformed",
                value=42,
            )
        )
        assert created["period_key"] == "2026"
        assert created["indicator_key"] == "override:custom_conformed"
    finally:
        settings.ANALYTICS_DB_PATH = original_path

    with factory() as session:
        observation = session.execute(select(InclusionObservation)).scalars().first()
        other_indicator = InclusionIndicator(
            code="different",
            label="Different",
        )
        session.add(other_indicator)
        session.flush()
        observation.indicator_code = other_indicator.code
        with pytest.raises(Exception, match="indicator_id/indicator_code mismatch"):
            session.commit()
