#!/bin/sh
set -eu

compose_project=${COMPOSE_PROJECT_NAME:-surendettement_staging_validation}
database=${POSTGRES_DB:-surendettement_staging}
user=${POSTGRES_USER:-surendettement_staging}
password=${POSTGRES_PASSWORD:-}
source_db=${SOURCE_SQLITE_DB:-data/processed/surendettement.db}
host_port=${POSTGRES_PORT:-5432}
report_dir=${POSTGRES_VALIDATION_REPORT_DIR:-app/reports}

case "$database" in
  *local*|*staging*|*test*) ;;
  *)
    printf 'Refused: POSTGRES_DB must contain local, staging, or test.\n' >&2
    exit 2
    ;;
esac

if [ -z "$password" ]; then
  printf 'Refused: POSTGRES_PASSWORD must be set explicitly.\n' >&2
  exit 2
fi

if ! command -v docker >/dev/null 2>&1; then
  printf 'Docker is required.\n' >&2
  exit 2
fi
if ! docker compose version >/dev/null 2>&1; then
  printf 'Docker Compose v2 is required.\n' >&2
  exit 2
fi
if ! docker info >/dev/null 2>&1; then
  printf 'Docker daemon is unavailable. Start Docker and retry.\n' >&2
  exit 2
fi
if [ ! -f "$source_db" ]; then
  printf 'SQLite source not found: %s\n' "$source_db" >&2
  exit 2
fi

export COMPOSE_PROJECT_NAME=$compose_project
export POSTGRES_DB=$database
export POSTGRES_USER=$user
export POSTGRES_PASSWORD=$password
export POSTGRES_PORT=$host_port

compose_files="-f docker/compose.yaml -f docker/compose.staging.yaml"
container_url="postgresql+psycopg://${user}:${password}@postgres:5432/${database}"

printf '+ docker compose %s up -d --wait --wait-timeout 60 postgres\n' "$compose_files"
if ! docker compose $compose_files up -d --wait --wait-timeout 60 postgres; then
  printf 'PostgreSQL did not become healthy within 60 seconds.\n' >&2
  docker compose $compose_files ps postgres >&2
  exit 1
fi

printf '+ docker compose %s ps\n' "$compose_files"
docker compose $compose_files ps

printf '+ PostgreSQL connection check\n'
docker compose $compose_files exec -T postgres \
  pg_isready --username "$user" --dbname "$database"

printf '+ schema migrations and dry-run\n'
docker compose $compose_files run --rm --no-deps api \
  python -m src.storage.migrate_to_postgres \
  --source "$source_db" \
  --target-url "$container_url" \
  --dry-run

if [ "${CONFIRM_LOCAL_MIGRATION:-no}" != "yes" ]; then
  printf '\nDry-run completed. Real copy was not executed.\n'
  printf 'Set CONFIRM_LOCAL_MIGRATION=yes and rerun to copy data.\n'
  printf 'No volume was removed. Stop with:\n'
  printf '  docker compose %s down\n' "$compose_files"
  exit 0
fi

printf '+ confirmed local migration\n'
docker compose $compose_files run --rm --no-deps api \
  python -m src.storage.migrate_to_postgres \
  --source "$source_db" \
  --target-url "$container_url"

printf '+ PostgreSQL integration tests\n'
docker compose $compose_files run --rm --no-deps \
  -e TEST_POSTGRES_DATABASE_URL="$container_url" \
  api python -m pytest -m postgres_integration -q

mkdir -p "$report_dir"
printf '+ data comparison and report generation\n'
docker compose $compose_files run --rm --no-deps -T \
  -e SOURCE_SQLITE_DB="$source_db" \
  -e TARGET_DATABASE_URL="$container_url" \
  -e REPORT_JSON="/workspace/$report_dir/postgres_migration_validation.json" \
  -e REPORT_MD="/workspace/$report_dir/postgres_migration_validation.md" \
  -v "$(pwd)/$report_dir:/workspace/$report_dir" \
  api python - <<'PY'
import json
import os
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import MetaData, create_engine, func, select, text

source = create_engine(f"sqlite:///{os.environ['SOURCE_SQLITE_DB']}")
target = create_engine(os.environ["TARGET_DATABASE_URL"])
source_meta = MetaData()
target_meta = MetaData()
source_meta.reflect(bind=source)
target_meta.reflect(bind=target)


def scalar(connection, statement):
    return connection.execute(statement).scalar()


def serializable(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def normalized_rows(connection, statement):
    return [
        [serializable(value) for value in row]
        for row in connection.execute(statement)
    ]


def compare_rows(left, right, numeric_tolerances):
    if len(left) != len(right):
        return False, {}
    maximum_differences = {index: 0.0 for index in numeric_tolerances}
    matches = True
    for left_row, right_row in zip(left, right):
        if len(left_row) != len(right_row):
            return False, maximum_differences
        for index, (left_value, right_value) in enumerate(
            zip(left_row, right_row)
        ):
            if index not in numeric_tolerances:
                matches = matches and left_value == right_value
                continue
            if left_value is None or right_value is None:
                matches = matches and left_value == right_value
                continue
            difference = abs(float(left_value) - float(right_value))
            maximum_differences[index] = max(
                maximum_differences[index],
                difference,
            )
            matches = matches and difference <= numeric_tolerances[index]
    return matches, maximum_differences


def table_summary(connection, table):
    pk = list(table.primary_key.columns)
    result = {"rows": scalar(connection, select(func.count()).select_from(table))}
    if len(pk) == 1:
        column = pk[0]
        result.update(
            distinct_primary_keys=scalar(
                connection, select(func.count(func.distinct(column)))
            ),
            minimum_primary_key=serializable(scalar(connection, select(func.min(column)))),
            maximum_primary_key=serializable(scalar(connection, select(func.max(column)))),
        )
    period_column = next(
        (
            table.c[name]
            for name in ("reference_period", "period_key", "year")
            if name in table.c
        ),
        None,
    )
    if period_column is not None:
        result["first_period"] = serializable(
            scalar(connection, select(func.min(period_column)))
        )
        result["last_period"] = serializable(
            scalar(connection, select(func.max(period_column)))
        )
    result["unexpected_nulls"] = {
        column.name: scalar(
            connection,
            select(func.count()).select_from(table).where(column.is_(None)),
        )
        for column in table.columns
        if not column.nullable
    }
    return result


common_tables = sorted(set(source_meta.tables) & set(target_meta.tables))
report = {
    "source": os.environ["SOURCE_SQLITE_DB"],
    "target": "postgresql",
    "status": "PASS",
    "tables": {},
    "domain_checks": {},
    "warnings": [],
    "errors": [],
}

with source.connect() as src, target.connect() as dst:
    for name in common_tables:
        src_summary = table_summary(src, source_meta.tables[name])
        dst_summary = table_summary(dst, target_meta.tables[name])
        matches = src_summary["rows"] == dst_summary["rows"]
        report["tables"][name] = {
            "sqlite": src_summary,
            "postgresql": dst_summary,
            "row_count_matches": matches,
        }
        if not matches:
            report["errors"].append(f"{name}: row count mismatch")

    if "observations" in source_meta.tables:
        observation_checks = {}
        for dimension in ("indicator_code", "geographic_level", "reference_period"):
            query = text(
                f"SELECT {dimension}, COUNT(*) AS count "
                f"FROM observations GROUP BY {dimension} ORDER BY {dimension}"
            )
            src_rows = normalized_rows(src, query)
            dst_rows = normalized_rows(dst, query)
            observation_checks[f"counts_by_{dimension}"] = {
                "matches": src_rows == dst_rows,
                "sqlite": src_rows,
                "postgresql": dst_rows,
            }
            if src_rows != dst_rows:
                report["errors"].append(
                    f"observations: counts by {dimension} mismatch"
                )
        duplicates = text(
            """
            SELECT COUNT(*) FROM (
                SELECT indicator_code, geographic_level, geographic_code,
                       reference_period, COUNT(*) AS n
                FROM observations
                GROUP BY indicator_code, geographic_level, geographic_code,
                         reference_period
                HAVING COUNT(*) > 1
            ) AS duplicates
            """
        )
        observation_checks["functional_duplicates"] = {
            "sqlite": scalar(src, duplicates),
            "postgresql": scalar(dst, duplicates),
        }
        missing_territories = text(
            """
            SELECT geographic_level, COUNT(*)
            FROM observations
            WHERE geographic_code IS NULL OR TRIM(geographic_code) = ''
            GROUP BY geographic_level ORDER BY geographic_level
            """
        )
        src_missing = normalized_rows(src, missing_territories)
        dst_missing = normalized_rows(dst, missing_territories)
        observation_checks["missing_territories"] = {
            "matches": src_missing == dst_missing,
            "sqlite": src_missing,
            "postgresql": dst_missing,
        }
        unit_query = text(
            """
            SELECT indicator_code, unit
            FROM observations
            GROUP BY indicator_code, unit
            ORDER BY indicator_code, unit
            """
        )
        src_units = normalized_rows(src, unit_query)
        dst_units = normalized_rows(dst, unit_query)
        observation_checks["units_by_indicator"] = {
            "matches": src_units == dst_units,
            "sqlite": src_units,
            "postgresql": dst_units,
        }
        report["domain_checks"]["observations"] = observation_checks

    if "risk_scores" in source_meta.tables:
        score_query = text(
            """
            SELECT risk_score_model_id, geographic_level, status, COUNT(*),
                   AVG(coverage_ratio)
            FROM risk_scores
            GROUP BY risk_score_model_id, geographic_level, status
            ORDER BY risk_score_model_id, geographic_level, status
            """
        )
        src_scores = normalized_rows(src, score_query)
        dst_scores = normalized_rows(dst, score_query)
        sample_query = text(
            """
            SELECT id, score, coverage_ratio, status
            FROM risk_scores
            ORDER BY id
            LIMIT 25
            """
        )
        src_sample = normalized_rows(src, sample_query)
        dst_sample = normalized_rows(dst, sample_query)
        sample_matches, sample_differences = compare_rows(
            src_sample,
            dst_sample,
            {1: 1e-8, 2: 1e-6},
        )
        report["domain_checks"]["risk_scores"] = {
            "distribution_matches": src_scores == dst_scores,
            "sqlite_distribution": src_scores,
            "postgresql_distribution": dst_scores,
            "deterministic_sample_matches": sample_matches,
            "maximum_score_difference": sample_differences.get(1),
            "maximum_coverage_difference": sample_differences.get(2),
        }
        if src_scores != dst_scores or not sample_matches:
            report["errors"].append("risk_scores: distribution or sample mismatch")

    if "risk_score_details" in source_meta.tables:
        detail_query = text(
            """
            SELECT id, risk_score_id, indicator_code, contribution,
                   effective_weight
            FROM risk_score_details
            ORDER BY id
            LIMIT 50
            """
        )
        src_details = normalized_rows(src, detail_query)
        dst_details = normalized_rows(dst, detail_query)
        detail_matches, detail_differences = compare_rows(
            src_details,
            dst_details,
            {3: 1e-8, 4: 1e-8},
        )
        report["domain_checks"]["risk_score_details"] = {
            "deterministic_sample_matches": detail_matches,
            "maximum_contribution_difference": detail_differences.get(3),
            "maximum_effective_weight_difference": detail_differences.get(4),
        }
        if not detail_matches:
            report["errors"].append("risk_score_details: sample mismatch")

    if "pipeline_runs" in source_meta.tables:
        run_query = text(
            """
            SELECT id, pipeline_name, status, started_at, finished_at
            FROM pipeline_runs ORDER BY started_at, id
            """
        )
        src_runs = normalized_rows(src, run_query)
        dst_runs = normalized_rows(dst, run_query)
        report["domain_checks"]["pipeline_runs"] = {
            "matches": src_runs == dst_runs,
            "sqlite": src_runs,
            "postgresql": dst_runs,
        }

    if "source_documents" in source_meta.tables:
        document_query = text(
            """
            SELECT extraction_status, COUNT(*)
            FROM source_documents
            WHERE extraction_status IN ('error', 'needs_review')
            GROUP BY extraction_status ORDER BY extraction_status
            """
        )
        report["domain_checks"]["documents_requiring_attention"] = {
            "sqlite": normalized_rows(src, document_query),
            "postgresql": normalized_rows(dst, document_query),
        }

if report["errors"]:
    report["status"] = "FAIL"
elif report["warnings"]:
    report["status"] = "PASS_WITH_WARNINGS"

json_path = Path(os.environ["REPORT_JSON"])
md_path = Path(os.environ["REPORT_MD"])
json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
lines = [
    "# PostgreSQL migration validation",
    "",
    f"Status: **{report['status']}**",
    "",
    "## Table volumes",
    "",
    "| Table | SQLite | PostgreSQL | Match |",
    "|---|---:|---:|:---:|",
]
for name, values in report["tables"].items():
    lines.append(
        f"| {name} | {values['sqlite']['rows']} | "
        f"{values['postgresql']['rows']} | "
        f"{'yes' if values['row_count_matches'] else 'no'} |"
    )
lines.extend(["", "## Errors", ""])
if report["errors"]:
    lines.extend(f"- {item}" for item in report["errors"])
else:
    lines.append("- None")
lines.extend(["", "## Warnings", ""])
if report["warnings"]:
    lines.extend(f"- {item}" for item in report["warnings"])
else:
    lines.append("- None")
md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(json.dumps({"status": report["status"], "json": str(json_path), "markdown": str(md_path)}))
raise SystemExit(0 if report["status"] in {"PASS", "PASS_WITH_WARNINGS"} else 1)
PY

printf '\nValidation completed. No volume was removed.\n'
printf 'Stop services without deleting data:\n'
printf '  docker compose %s down\n' "$compose_files"
printf 'Optional manual cleanup after inspection only:\n'
printf '  docker compose %s down --volumes\n' "$compose_files"
