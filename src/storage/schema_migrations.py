"""Small versioned migration registry compatible with SQLite and PostgreSQL."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy import Engine, inspect, text

from src.storage.database import get_engine
from src.storage.models import Base


@dataclass(slots=True)
class MigrationReport:
    applied: list[str]
    already_applied: list[str]


def apply_migrations(engine: Engine | None = None) -> MigrationReport:
    engine = engine or get_engine()
    applied, already_applied = [], []
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version VARCHAR(64) PRIMARY KEY,
                    description VARCHAR(512) NOT NULL,
                    applied_at VARCHAR(32) NOT NULL
                )
                """
            )
        )
        known = {
            row[0]
            for row in connection.execute(
                text("SELECT version FROM schema_migrations")
            )
        }
        for version, description, operation in MIGRATIONS:
            if version in known:
                already_applied.append(version)
                continue
            operation(connection)
            connection.execute(
                text(
                    """
                    INSERT INTO schema_migrations(version, description, applied_at)
                    VALUES (:version, :description, :applied_at)
                    """
                ),
                {
                    "version": version,
                    "description": description,
                    "applied_at": _now(),
                },
            )
            applied.append(version)
    return MigrationReport(applied=applied, already_applied=already_applied)


def report_as_dict(report: MigrationReport) -> dict:
    return asdict(report)


def _create_application_schema(connection) -> None:
    Base.metadata.create_all(bind=connection)


def _create_operational_indexes(connection) -> None:
    statements = (
        """
        CREATE INDEX IF NOT EXISTS ix_pipeline_runs_name_started
        ON pipeline_runs(pipeline_name, started_at)
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_source_documents_period_status
        ON source_documents(reference_period, extraction_status)
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_observations_period_level_code
        ON observations(reference_period, geographic_level, geographic_code)
        """,
    )
    for statement in statements:
        connection.execute(text(statement))


def _create_readonly_analytics_views(connection) -> None:
    statements = (
        """
        CREATE VIEW analytics_risk_scores AS
        SELECT
            rs.id,
            rs.geographic_level,
            rs.geographic_code,
            rs.geographic_name,
            rs.reference_period,
            rs.score,
            rs.risk_level,
            rs.coverage_ratio,
            rs.status,
            model.code AS model_code,
            model.version AS model_version,
            model.is_active AS model_is_active,
            rs.calculated_at
        FROM risk_scores AS rs
        JOIN risk_score_models AS model
          ON model.id = rs.risk_score_model_id
        """,
        """
        CREATE VIEW analytics_score_factors AS
        SELECT
            detail.id,
            score.geographic_level,
            score.geographic_code,
            score.geographic_name,
            score.reference_period,
            model.code AS model_code,
            model.version AS model_version,
            detail.indicator_code,
            detail.raw_value,
            detail.unit,
            detail.normalized_value,
            detail.configured_weight,
            detail.effective_weight,
            detail.contribution,
            detail.direction
        FROM risk_score_details AS detail
        JOIN risk_scores AS score ON score.id = detail.risk_score_id
        JOIN risk_score_models AS model
          ON model.id = score.risk_score_model_id
        """,
        """
        CREATE VIEW analytics_observations AS
        SELECT
            observation.id,
            observation.indicator_code,
            indicator.label AS indicator_label,
            observation.geographic_level,
            observation.geographic_code,
            observation.geographic_name,
            observation.region_code,
            observation.reference_period,
            observation.value_numeric,
            observation.unit,
            observation.observation_type,
            observation.comparison_period,
            observation.variation_numeric,
            observation.variation_unit,
            observation.confidence_score,
            observation.updated_at
        FROM observations AS observation
        JOIN indicators AS indicator ON indicator.id = observation.indicator_id
        """,
        """
        CREATE VIEW analytics_model_comparisons AS
        SELECT
            score_a.geographic_level,
            score_a.geographic_code,
            score_a.geographic_name,
            score_a.reference_period,
            model_a.code AS model_code,
            model_a.version AS version_a,
            model_b.version AS version_b,
            score_a.score AS score_a,
            score_b.score AS score_b,
            score_b.score - score_a.score AS score_change
        FROM risk_scores AS score_a
        JOIN risk_score_models AS model_a
          ON model_a.id = score_a.risk_score_model_id
        JOIN risk_scores AS score_b
          ON score_b.geographic_level = score_a.geographic_level
         AND score_b.geographic_code = score_a.geographic_code
         AND score_b.reference_period = score_a.reference_period
        JOIN risk_score_models AS model_b
          ON model_b.id = score_b.risk_score_model_id
         AND model_b.code = model_a.code
         AND model_b.version > model_a.version
        """,
        """
        CREATE VIEW analytics_pipeline_status AS
        SELECT
            id,
            pipeline_name,
            status,
            started_at,
            finished_at
        FROM pipeline_runs
        """,
    )
    existing_views = set(inspect(connection).get_view_names())
    for statement in statements:
        view_name = statement.split("CREATE VIEW", 1)[1].split("AS", 1)[0].strip()
        if view_name not in existing_views:
            connection.execute(text(statement))


def _create_macro_region_analytics_view(connection) -> None:
    if connection.dialect.name != "postgresql":
        return
    if "v_insee_macro_region_selected" not in inspect(connection).get_view_names():
        raise RuntimeError(
            "La vue source v_insee_macro_region_selected est absente."
        )
    connection.execute(
        text(
            """
            CREATE OR REPLACE VIEW analytics_macro_regions AS
            SELECT
                reference_year,
                region_name,
                indicator_code,
                indicator_name,
                indicator_group,
                aggregation_rule,
                value AS value_numeric
            FROM v_insee_macro_region_selected
            """
        )
    )


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


Migration = tuple[str, str, Callable]
MIGRATIONS: tuple[Migration, ...] = (
    (
        "001_application_schema",
        "Create the operational SQLAlchemy schema",
        _create_application_schema,
    ),
    (
        "002_operational_indexes",
        "Add pipeline, source and observation lookup indexes",
        _create_operational_indexes,
    ),
    (
        "003_readonly_analytics_views",
        "Create the allow-listed read-only analytics views",
        _create_readonly_analytics_views,
    ),
    (
        "004_macro_region_analytics_view",
        "Expose selected regional macro indicators as a read-only view",
        _create_macro_region_analytics_view,
    ),
)
