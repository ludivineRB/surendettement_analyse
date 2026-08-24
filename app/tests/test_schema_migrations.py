from sqlalchemy import create_engine, inspect, text

from src.storage.schema_migrations import apply_migrations


def test_schema_migrations_are_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'migrations.db'}")
    first = apply_migrations(engine)
    second = apply_migrations(engine)
    assert first.applied == [
        "001_application_schema",
        "002_operational_indexes",
        "003_readonly_analytics_views",
        "004_macro_region_analytics_view",
    ]
    assert second.already_applied == first.applied
    assert "pipeline_runs" in inspect(engine).get_table_names()
    with engine.connect() as connection:
        versions = connection.execute(
            text("SELECT COUNT(*) FROM schema_migrations")
        ).scalar_one()
    assert versions == 4
