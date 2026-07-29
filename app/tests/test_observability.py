from pathlib import Path

from app.tests.test_analytics_bridge import _operational_factory
from app.tests.views.test_analytics_api import _create_test_analytics_db
from src.observability import build_observability_report
from src.storage.conformed_dimensions import migrate_conformed_dimensions


def test_observability_reports_freshness_integrity_and_missing_data(
    tmp_path: Path,
):
    analytics_path = tmp_path / "analytics.db"
    operational_path = tmp_path / "operational.db"
    _create_test_analytics_db(analytics_path)
    _operational_factory(operational_path)
    migrate_conformed_dimensions(analytics_path, operational_path)

    report = build_observability_report(operational_path, analytics_path)

    assert report["generated_at"]
    assert report["operational"]["counts"]["observations"] == 1
    assert report["operational"]["integrity"] == {
        "foreign_key_violations": 0,
        "indicator_code_mismatches": 0,
    }
    assert report["analytics"]["counts"]["dim_region"] == 13
    assert report["analytics"]["integrity"] == {
        "foreign_key_violations": 0,
        "departments_without_region": 0,
    }
    assert report["operational"]["missing_regional_dossiers"]
