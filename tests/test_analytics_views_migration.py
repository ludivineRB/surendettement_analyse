from sqlalchemy import create_engine, inspect, text

from src.storage.schema_migrations import apply_migrations


EXPECTED_VIEWS = {
    "analytics_risk_scores",
    "analytics_score_factors",
    "analytics_observations",
    "analytics_model_comparisons",
    "analytics_pipeline_status",
}


def test_analytics_views_are_created_and_migration_is_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'views.db'}")

    first = apply_migrations(engine)
    second = apply_migrations(engine)

    assert "003_readonly_analytics_views" in first.applied
    assert "003_readonly_analytics_views" in second.already_applied
    assert EXPECTED_VIEWS <= set(inspect(engine).get_view_names())
    with engine.connect() as connection:
        for view in EXPECTED_VIEWS:
            connection.execute(text(f"SELECT * FROM {view} LIMIT 1")).all()
