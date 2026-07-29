"""Read-only health report for data sources, models and score coverage."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text

from src.storage.conformed_dimensions import ANALYTICS_DB
from src.storage.database import get_database_url


def build_observability_report(
    operational_db: Path | None = None,
    analytics_db: Path = ANALYTICS_DB,
) -> dict:
    database_url = get_database_url()
    report = {
        "generated_at": datetime.now(timezone.utc).replace(
            microsecond=0
        ).isoformat(),
        "status": "ok",
        "operational": {},
        "analytics": {},
        "alerts": [],
    }
    if operational_db is not None or database_url.startswith("sqlite:///"):
        sqlite_path = operational_db or _sqlite_path(database_url)
        with sqlite3.connect(sqlite_path) as connection:
            connection.row_factory = sqlite3.Row
            _operational_report(connection, report)
    else:
        with create_engine(database_url).connect() as connection:
            _operational_report(connection, report)
    with sqlite3.connect(analytics_db) as connection:
        connection.row_factory = sqlite3.Row
        _analytics_report(connection, report)
    if report["alerts"]:
        report["status"] = "warning"
    return report


def _operational_report(connection: sqlite3.Connection, report: dict) -> None:
    operational = report["operational"]
    operational["counts"] = {
        table: _count(connection, table)
        for table in (
            "source_documents",
            "indicators",
            "observations",
            "risk_scores",
            "risk_score_details",
            "pipeline_runs",
        )
    }
    operational["active_model"] = _one(
        connection,
        """
        SELECT code, version, minimum_coverage_ratio, updated_at
        FROM risk_score_models WHERE is_active = 1
        ORDER BY id DESC LIMIT 1
        """,
    )
    operational["document_statuses"] = _all(
        connection,
        """
        SELECT extraction_status AS status, COUNT(*) AS count,
               MAX(reference_period) AS latest_period
        FROM source_documents
        GROUP BY extraction_status ORDER BY extraction_status
        """,
    )
    operational["indicator_freshness"] = _all(
        connection,
        """
        SELECT i.code AS indicator_code, i.label AS indicator_label,
               COUNT(*) AS observations,
               MIN(o.reference_period) AS first_period,
               MAX(o.reference_period) AS latest_period,
               COUNT(DISTINCT o.geographic_code) AS territories,
               MAX(o.updated_at) AS last_updated_at
        FROM observations o
        JOIN indicators i ON i.id = o.indicator_id
        GROUP BY i.id, i.code, i.label
        ORDER BY i.code
        """,
    )
    operational["score_statuses"] = _all(
        connection,
        """
        SELECT geographic_level, status, COUNT(*) AS count,
               ROUND(AVG(coverage_ratio), 4) AS average_coverage,
               MIN(reference_period) AS first_period,
               MAX(reference_period) AS latest_period
        FROM risk_scores
        GROUP BY geographic_level, status
        ORDER BY geographic_level, status
        """,
    )
    operational["pipeline_versions"] = _all(
        connection,
        """
        SELECT extractor_version, extraction_status, COUNT(*) AS documents,
               MAX(reference_period) AS latest_period
        FROM source_documents
        GROUP BY extractor_version, extraction_status
        ORDER BY extractor_version, extraction_status
        """,
    )
    operational["pipeline_runs"] = _all(
        connection,
        """
        SELECT id, pipeline_name, status, started_at, finished_at,
               error_message
        FROM pipeline_runs
        ORDER BY id DESC LIMIT 20
        """,
    )
    operational["missing_regional_dossiers"] = _all(
        connection,
        """
        SELECT r.region_code, r.region_name, p.period_key AS reference_period
        FROM dim_region r
        CROSS JOIN dim_period p
        WHERE p.granularity = 'month'
          AND NOT EXISTS (
              SELECT 1
              FROM observations o
              JOIN indicators i ON i.id = o.indicator_id
              WHERE o.geographic_level = 'region'
                AND o.geographic_code = r.region_code
                AND o.reference_period = p.period_key
                AND i.code = 'surendettement_dossiers_deposes'
          )
        ORDER BY p.period_key, r.region_code
        """,
    )
    operational["needs_review"] = _all(
        connection,
        """
        SELECT region_code, region_name, reference_period, pdf_filename,
               page_url, pdf_url
        FROM source_documents
        WHERE extraction_status <> 'success'
        ORDER BY reference_period DESC, region_code
        """,
    )
    indicator_mismatches = _execute(
        connection,
        """
        SELECT COUNT(*)
        FROM observations o JOIN indicators i ON i.id = o.indicator_id
        WHERE o.indicator_code <> i.code
        """
    ).fetchone()[0]
    operational["integrity"] = {
        "foreign_key_violations": _foreign_key_violations(connection),
        "indicator_code_mismatches": indicator_mismatches,
    }
    if operational["needs_review"]:
        report["alerts"].append(
            {
                "severity": "warning",
                "code": "documents_needing_review",
                "message": (
                    f"{len(operational['needs_review'])} document(s) "
                    "nécessitent une vérification."
                ),
            }
        )
    if operational["missing_regional_dossiers"]:
        report["alerts"].append(
            {
                "severity": "warning",
                "code": "missing_regional_dossiers",
                "message": (
                    f"{len(operational['missing_regional_dossiers'])} "
                    "couple(s) région-mois sans dossiers."
                ),
            }
        )
    if indicator_mismatches:
        report["alerts"].append(
            {
                "severity": "error",
                "code": "indicator_mismatch",
                "message": f"{indicator_mismatches} incohérence(s) indicateur.",
            }
        )


def _analytics_report(connection: sqlite3.Connection, report: dict) -> None:
    analytics = report["analytics"]
    analytics["counts"] = {
        table: _count(connection, table)
        for table in (
            "dim_region",
            "dim_department",
            "dim_period",
            "dim_indicator",
            "fact_insee_macro",
            "fact_bdf_statinfo",
            "fact_macro_override",
            "fact_surendettement",
        )
    }
    analytics["deprecated_objects"] = _all(
        connection,
        """
        SELECT object_name, object_type, deprecated_since, replacement, reason
        FROM schema_deprecations ORDER BY object_name
        """,
    )
    analytics["integrity"] = {
        "foreign_key_violations": len(
            connection.execute("PRAGMA foreign_key_check").fetchall()
        ),
        "departments_without_region": connection.execute(
            "SELECT COUNT(*) FROM dim_department WHERE region_code IS NULL"
        ).fetchone()[0],
    }
    if any(analytics["integrity"].values()):
        report["alerts"].append(
            {
                "severity": "error",
                "code": "analytics_integrity",
                "message": "La base analytique présente une anomalie d'intégrité.",
            }
        )


def _sqlite_path(url: str) -> Path:
    if not url.startswith("sqlite:///"):
        raise ValueError("Observability currently requires SQLite")
    return Path(url.removeprefix("sqlite:///"))


def _count(connection: sqlite3.Connection, table: str) -> int:
    return _execute(connection, f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def _all(connection: sqlite3.Connection, query: str) -> list[dict]:
    return [_row_dict(row) for row in _execute(connection, query).fetchall()]


def _one(connection: sqlite3.Connection, query: str) -> dict | None:
    row = _execute(connection, query).fetchone()
    return _row_dict(row) if row else None


def _execute(connection, query: str):
    if isinstance(connection, sqlite3.Connection):
        return connection.execute(query)
    return connection.execute(text(query))


def _row_dict(row) -> dict:
    return dict(row) if isinstance(row, sqlite3.Row) else dict(row._mapping)


def _foreign_key_violations(connection) -> int:
    if isinstance(connection, sqlite3.Connection):
        return len(connection.execute("PRAGMA foreign_key_check").fetchall())
    # PostgreSQL enforces declared foreign keys on every write.
    return 0
