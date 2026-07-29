"""Idempotent migration to conformed geography and period dimensions."""

from __future__ import annotations

import argparse
import re
import sqlite3
import unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from src.storage.database import get_database_url

ANALYTICS_DB = Path(
    "data/processed/analytics/surendettement_macro_analytics.db"
)
MIGRATION_VERSION = "conformed-dimensions-v1"

REGIONS = {
    "11": "Île-de-France",
    "24": "Centre-Val de Loire",
    "27": "Bourgogne-Franche-Comté",
    "28": "Normandie",
    "32": "Hauts-de-France",
    "44": "Grand Est",
    "52": "Pays de la Loire",
    "53": "Bretagne",
    "75": "Nouvelle-Aquitaine",
    "76": "Occitanie",
    "84": "Auvergne-Rhône-Alpes",
    "93": "Provence-Alpes-Côte d’Azur",
    "94": "Corse",
}


@dataclass(slots=True)
class MigrationReport:
    migration_version: str = MIGRATION_VERSION
    analytics_regions: int = 0
    analytics_periods: int = 0
    operational_regions: int = 0
    operational_periods: int = 0
    indicator_mismatches: int = 0
    deprecated_objects: int = 0


def migrate_conformed_dimensions(
    analytics_db: Path = ANALYTICS_DB,
    operational_db: Path | None = None,
) -> MigrationReport:
    """Migrate both SQLite databases without deleting historical data."""
    operational_db = operational_db or _sqlite_path_from_url(get_database_url())
    report = MigrationReport()
    with sqlite3.connect(analytics_db) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        _migrate_analytics(connection)
        report.analytics_regions = _count(connection, "dim_region")
        report.analytics_periods = _count(connection, "dim_period")
        report.deprecated_objects = _count(connection, "schema_deprecations")
        connection.commit()
    with sqlite3.connect(operational_db) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        _migrate_operational(connection)
        report.operational_regions = _count(connection, "dim_region")
        report.operational_periods = _count(connection, "dim_period")
        report.indicator_mismatches = connection.execute(
            """
            SELECT COUNT(*)
            FROM observations o
            JOIN indicators i ON i.id = o.indicator_id
            WHERE o.indicator_code <> i.code
            """
        ).fetchone()[0]
        connection.commit()
    return report


def _migrate_analytics(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS dim_region (
            region_code TEXT PRIMARY KEY,
            region_name TEXT NOT NULL UNIQUE,
            is_metropolitan_scope INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS dim_period (
            period_key TEXT PRIMARY KEY,
            reference_year INTEGER NOT NULL,
            reference_month_number INTEGER,
            granularity TEXT NOT NULL
                CHECK (granularity IN ('month', 'year')),
            CHECK (
                (granularity = 'month' AND reference_month_number BETWEEN 1 AND 12)
                OR (granularity = 'year' AND reference_month_number IS NULL)
            )
        );
        CREATE TABLE IF NOT EXISTS schema_deprecations (
            object_name TEXT PRIMARY KEY,
            object_type TEXT NOT NULL,
            deprecated_since TEXT NOT NULL,
            replacement TEXT,
            reason TEXT NOT NULL
        );
        """
    )
    connection.executemany(
        """
        INSERT INTO dim_region(region_code, region_name, is_metropolitan_scope)
        VALUES (?, ?, 1)
        ON CONFLICT(region_code) DO UPDATE SET region_name = excluded.region_name
        """,
        REGIONS.items(),
    )
    if not _has_column(connection, "dim_department", "region_code"):
        connection.execute("ALTER TABLE dim_department ADD COLUMN region_code TEXT")
    region_codes_by_name = {
        _normalize_name(name): code for code, name in REGIONS.items()
    }
    for department_code, region_name in connection.execute(
        "SELECT departement_code, region_name FROM dim_department"
    ):
        region_code = region_codes_by_name.get(_normalize_name(region_name))
        if region_code:
            connection.execute(
                """
                UPDATE dim_department SET region_code = ?
                WHERE departement_code = ?
                """,
                (region_code, department_code),
            )
    connection.execute(
        """
        INSERT OR IGNORE INTO dim_period(
            period_key, reference_year, reference_month_number, granularity
        )
        SELECT DISTINCT
            reference_period, reference_year, reference_month_number, 'month'
        FROM fact_bdf_statinfo
        """
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO dim_period(
            period_key, reference_year, reference_month_number, granularity
        )
        SELECT DISTINCT CAST(reference_year AS TEXT), reference_year, NULL, 'year'
        FROM fact_insee_macro
        """
    )
    connection.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_department_region_code
            ON dim_department(region_code);
        CREATE TRIGGER IF NOT EXISTS trg_department_region_insert
        BEFORE INSERT ON dim_department
        WHEN NEW.region_code IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM dim_region WHERE region_code = NEW.region_code
          )
        BEGIN
            SELECT RAISE(ABORT, 'unknown dim_department.region_code');
        END;
        CREATE TRIGGER IF NOT EXISTS trg_department_region_update
        BEFORE UPDATE OF region_code ON dim_department
        WHEN NEW.region_code IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM dim_region WHERE region_code = NEW.region_code
          )
        BEGIN
            SELECT RAISE(ABORT, 'unknown dim_department.region_code');
        END;
        """
    )
    _migrate_override_table(connection)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    connection.executemany(
        """
        INSERT INTO schema_deprecations(
            object_name, object_type, deprecated_since, replacement, reason
        ) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(object_name) DO NOTHING
        """,
        [
            (
                "fact_surendettement",
                "table",
                now,
                "operational.observations",
                "Modèle départemental historique vide",
            ),
            (
                "v_surendettement_annual",
                "view",
                now,
                "operational.observations",
                "Vue fondée sur un fait historique vide",
            ),
            (
                "v_surendettement_with_insee_macro",
                "view",
                now,
                "risk_score analytics bridge",
                "Rapprochement historique remplacé par la passerelle versionnée",
            ),
        ],
    )
    _recreate_region_views(connection)


def _migrate_override_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS fact_macro_override (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            period_key TEXT NOT NULL,
            reference_year INTEGER NOT NULL,
            departement_code TEXT NOT NULL,
            indicator_key TEXT NOT NULL,
            indicator_code TEXT NOT NULL,
            indicator_name TEXT,
            indicator_group TEXT,
            value REAL NOT NULL,
            source_note TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(period_key) REFERENCES dim_period(period_key),
            FOREIGN KEY(departement_code)
                REFERENCES dim_department(departement_code),
            FOREIGN KEY(indicator_key) REFERENCES dim_indicator(indicator_key)
        )
        """
    )
    if not _has_column(connection, "fact_macro_override", "period_key"):
        rows = connection.execute(
            "SELECT * FROM fact_macro_override ORDER BY id"
        ).fetchall()
        connection.execute("ALTER TABLE fact_macro_override RENAME TO fact_macro_override_legacy")
        connection.execute(
            """
            CREATE TABLE fact_macro_override (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                period_key TEXT NOT NULL,
                reference_year INTEGER NOT NULL,
                departement_code TEXT NOT NULL,
                indicator_key TEXT NOT NULL,
                indicator_code TEXT NOT NULL,
                indicator_name TEXT,
                indicator_group TEXT,
                value REAL NOT NULL,
                source_note TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(period_key) REFERENCES dim_period(period_key),
                FOREIGN KEY(departement_code)
                    REFERENCES dim_department(departement_code),
                FOREIGN KEY(indicator_key) REFERENCES dim_indicator(indicator_key)
            )
            """
        )
        for row in rows:
            (
                row_id,
                year,
                department,
                code,
                name,
                group,
                value,
                note,
                created,
                updated,
            ) = row
            key = f"override:{code}"
            connection.execute(
                """
                INSERT OR IGNORE INTO dim_indicator(
                    indicator_key, source_system, indicator_code,
                    indicator_name, indicator_group, aggregation_rule
                ) VALUES (?, 'override', ?, ?, ?, 'manual')
                """,
                (key, code, name, group),
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO dim_period VALUES (?, ?, NULL, 'year')
                """,
                (str(year), year),
            )
            connection.execute(
                """
                INSERT INTO fact_macro_override VALUES(
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    row_id,
                    str(year),
                    year,
                    department,
                    key,
                    code,
                    name,
                    group,
                    value,
                    note,
                    created,
                    updated,
                ),
            )
        connection.execute("DROP TABLE fact_macro_override_legacy")
    connection.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_macro_override_lookup
            ON fact_macro_override(period_key, departement_code, indicator_key);
        """
    )


def _recreate_region_views(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        DROP VIEW IF EXISTS v_insee_macro_region_selected;
        DROP VIEW IF EXISTS v_insee_macro_region;
        CREATE VIEW v_insee_macro_region AS
        SELECT
            m.reference_year,
            r.region_code,
            r.region_name,
            i.indicator_code,
            i.indicator_name,
            i.indicator_group,
            i.aggregation_rule,
            SUM(m.value) AS value
        FROM fact_insee_macro m
        JOIN dim_department d ON d.departement_code = m.departement_code
        JOIN dim_region r ON r.region_code = d.region_code
        JOIN dim_indicator i ON i.indicator_key = m.indicator_key
        WHERE i.source_system = 'insee_macro'
        GROUP BY
            m.reference_year, r.region_code, r.region_name,
            i.indicator_code, i.indicator_name, i.indicator_group,
            i.aggregation_rule;

        CREATE VIEW v_insee_macro_region_selected AS
        WITH ratio_definitions(
            indicator_code, indicator_name, indicator_group,
            numerator_code, denominator_code
        ) AS (
            VALUES
                ('part_population_0014', 'Part de la population de 0 à 14 ans', 'démographie', 'P22_POP0014', 'P22_POP'),
                ('part_population_1529', 'Part de la population de 15 à 29 ans', 'démographie', 'P22_POP1529', 'P22_POP'),
                ('part_population_3044', 'Part de la population de 30 à 44 ans', 'démographie', 'P22_POP3044', 'P22_POP'),
                ('part_population_4559', 'Part de la population de 45 à 59 ans', 'démographie', 'P22_POP4559', 'P22_POP'),
                ('part_population_6074', 'Part de la population de 60 à 74 ans', 'démographie', 'P22_POP6074', 'P22_POP'),
                ('part_population_7589', 'Part de la population de 75 à 89 ans', 'démographie', 'P22_POP7589', 'P22_POP'),
                ('part_population_90p', 'Part de la population de 90 ans ou plus', 'démographie', 'P22_POP90P', 'P22_POP'),
                ('taux_activite_1564', 'Taux d’activité des 15 à 64 ans', 'emploi_chômage', 'P22_ACT1564', 'P22_POP1564'),
                ('taux_emploi_1564', 'Taux d’emploi des 15 à 64 ans', 'emploi_chômage', 'P22_ACTOCC1564', 'P22_POP1564'),
                ('taux_chomage_1564', 'Taux de chômage des 15 à 64 ans', 'emploi_chômage', 'P22_CHOM1564', 'P22_ACT1564'),
                ('part_residences_principales', 'Part des résidences principales', 'logement', 'P22_RP', 'P22_LOG'),
                ('part_residences_secondaires', 'Part des résidences secondaires', 'logement', 'P22_RSECOCC', 'P22_LOG'),
                ('part_logements_vacants', 'Part des logements vacants', 'logement', 'P22_LOGVAC', 'P22_LOG'),
                ('part_proprietaires', 'Part des résidences principales occupées par des propriétaires', 'logement', 'P22_RP_PROP', 'P22_RP'),
                ('part_locataires', 'Part des résidences principales occupées par des locataires', 'logement', 'P22_RP_LOC', 'P22_RP'),
                ('part_menages_seuls', 'Part des ménages d’une personne', 'familles', 'C22_MENPSEUL', 'C22_MEN'),
                ('part_familles_monoparentales', 'Part des familles monoparentales', 'familles', 'C22_FAMMONO', 'C22_FAM'),
                ('part_sans_diplome', 'Part des personnes sans diplôme ou titulaires au plus du CEP', 'formation', 'P22_NSCOL15P_DIPLMIN', 'P22_NSCOL15P'),
                ('part_diplomees_bac5', 'Part des diplômés Bac +5 ou plus', 'formation', 'P22_NSCOL15P_SUP5', 'P22_NSCOL15P')
        ),
        derived AS (
            SELECT
                numerator.reference_year,
                numerator.region_code,
                numerator.region_name,
                definitions.indicator_code,
                definitions.indicator_name,
                definitions.indicator_group,
                'derived_ratio' AS aggregation_rule,
                100.0 * numerator.value / NULLIF(denominator.value, 0) AS value
            FROM ratio_definitions definitions
            JOIN v_insee_macro_region numerator
              ON numerator.indicator_code = definitions.numerator_code
            JOIN v_insee_macro_region denominator
              ON denominator.reference_year = numerator.reference_year
             AND denominator.region_code = numerator.region_code
             AND denominator.indicator_code = definitions.denominator_code
        )
        SELECT reference_year, region_code, region_name, indicator_code,
               indicator_name, indicator_group, aggregation_rule, value
        FROM v_insee_macro_region
        UNION ALL
        SELECT reference_year, region_code, region_name, indicator_code,
               indicator_name, indicator_group, aggregation_rule, value
        FROM derived;
        """
    )


def _migrate_operational(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS dim_region (
            region_code TEXT PRIMARY KEY,
            region_name TEXT NOT NULL UNIQUE,
            is_metropolitan_scope INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS dim_period (
            period_key TEXT PRIMARY KEY,
            reference_year INTEGER NOT NULL,
            reference_month_number INTEGER,
            granularity TEXT NOT NULL
                CHECK (granularity IN ('month', 'year'))
        );
        """
    )
    connection.executemany(
        """
        INSERT INTO dim_region(region_code, region_name, is_metropolitan_scope)
        VALUES (?, ?, 1)
        ON CONFLICT(region_code) DO UPDATE SET region_name = excluded.region_name
        """,
        REGIONS.items(),
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO dim_period
        SELECT DISTINCT reference_period,
               CAST(SUBSTR(reference_period, 1, 4) AS INTEGER),
               CASE WHEN LENGTH(reference_period) = 7
                    THEN CAST(SUBSTR(reference_period, 6, 2) AS INTEGER) END,
               CASE WHEN LENGTH(reference_period) = 7 THEN 'month' ELSE 'year' END
        FROM (
            SELECT reference_period FROM observations
            UNION SELECT reference_period FROM source_documents
            UNION SELECT reference_period FROM risk_scores
        )
        """
    )
    connection.executescript(
        """
        CREATE TRIGGER IF NOT EXISTS trg_observation_indicator_insert
        BEFORE INSERT ON observations
        WHEN NEW.indicator_code <> (
            SELECT code FROM indicators WHERE id = NEW.indicator_id
        )
        BEGIN
            SELECT RAISE(ABORT, 'indicator_id/indicator_code mismatch');
        END;
        CREATE TRIGGER IF NOT EXISTS trg_observation_indicator_update
        BEFORE UPDATE OF indicator_id, indicator_code ON observations
        WHEN NEW.indicator_code <> (
            SELECT code FROM indicators WHERE id = NEW.indicator_id
        )
        BEGIN
            SELECT RAISE(ABORT, 'indicator_id/indicator_code mismatch');
        END;
        """
    )


def _sqlite_path_from_url(url: str) -> Path:
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        raise ValueError("Conformed dimension migration currently requires SQLite")
    return Path(url.removeprefix(prefix))


def _has_column(connection: sqlite3.Connection, table: str, column: str) -> bool:
    return column in {
        row[1] for row in connection.execute(f"PRAGMA table_info({table})")
    }


def _count(connection: sqlite3.Connection, table: str) -> int:
    return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def _normalize_name(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or "").lower())
    ascii_value = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return re.sub(r"[^a-z0-9]+", "", ascii_value)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analytics-db", type=Path, default=ANALYTICS_DB)
    parser.add_argument("--operational-db", type=Path)
    args = parser.parse_args()
    print(
        asdict(
            migrate_conformed_dimensions(
                args.analytics_db, args.operational_db
            )
        )
    )


if __name__ == "__main__":
    main()
