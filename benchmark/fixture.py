"""Deterministic SQLite fixture for the dataset's analytical views."""

from __future__ import annotations

from pathlib import Path
import sqlite3


SCHEMA = """
CREATE TABLE analytics_risk_scores (
 geographic_level TEXT, geographic_code TEXT, reference_period TEXT, score REAL
);
CREATE TABLE analytics_macro_regions (
 region_name TEXT, reference_year INTEGER, indicator_code TEXT, value_numeric REAL
);
CREATE TABLE analytics_score_factors (
 geographic_level TEXT, geographic_code TEXT, reference_period TEXT,
 indicator_code TEXT, contribution REAL
);
CREATE TABLE analytics_model_comparisons (
 geographic_level TEXT, geographic_code TEXT, reference_period TEXT,
 version_a TEXT, version_b TEXT, score_a REAL, score_b REAL, score_change REAL
);
CREATE TABLE analytics_observations (
 indicator_code TEXT, value_numeric REAL, reference_period TEXT
);
CREATE TABLE analytics_pipeline_status (dataset_name TEXT, refreshed_at TEXT);
"""


def initialise(path: Path) -> Path:
    if path.exists():
        raise FileExistsError(f"fixture target already exists: {path}")
    with sqlite3.connect(path) as connection:
        connection.executescript(SCHEMA)
        connection.executemany("INSERT INTO analytics_risk_scores VALUES (?,?,?,?)", [
            ("region", "11", "2025-02", 30.0), ("region", "32", "2025-02", 60.0),
            ("region", "11", "2025", 20.0), ("region", "32", "2025", 40.0),
            ("department", "59", "2024-02", 55.0),
            ("department", "59", "2025-02", 70.0),
            ("department", "75", "2025-02", 50.0),
        ])
        connection.executemany("INSERT INTO analytics_macro_regions VALUES (?,?,?,?)", [
            ("Hauts-de-France", 2022, "taux_chomage_1564", 9.0),
            ("Île-de-France", 2022, "taux_chomage_1564", 7.0),
            ("Hauts-de-France", 2022, "part_familles_monoparentales", 14.0),
            ("Île-de-France", 2022, "part_familles_monoparentales", 10.0),
        ])
        connection.executemany("INSERT INTO analytics_score_factors VALUES (?,?,?,?,?)", [
            ("region", "32", "2025-02", "taux_pauvrete", 18.0),
            ("region", "32", "2025-02", "taux_chomage", 12.0),
        ])
        connection.executemany("INSERT INTO analytics_model_comparisons VALUES (?,?,?,?,?,?,?,?)", [
            ("department", "59", "2025-02", "1.1.0", "1.2.0", 65.0, 70.0, 5.0),
            ("department", "75", "2025-02", "1.1.0", "1.2.0", 52.0, 50.0, -2.0),
        ])
        connection.execute("INSERT INTO analytics_pipeline_status VALUES (?,?)",
                           ("analytics", "2026-08-26T00:00:00Z"))
    return path


def execute(path: Path, sql: str) -> list[dict[str, object]]:
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute(sql).fetchall()]


def schema_text(path: Path) -> str:
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
        rows = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    return "\n".join(row[0] for row in rows if row[0])
