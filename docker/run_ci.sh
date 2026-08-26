#!/bin/sh
set -eu

export POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-ci-ephemeral-password}
export POSTGRES_DB=${POSTGRES_DB:-surendettement_ci_test}
export POSTGRES_USER=${POSTGRES_USER:-surendettement_ci}
export DJANGO_SECRET_KEY=${DJANGO_SECRET_KEY:-ci-only-django-secret-key-not-for-production}
export ASSISTANT_INTERNAL_TOKEN=${ASSISTANT_INTERNAL_TOKEN:-ci-only-internal-token}
export GRAFANA_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD:-ci-only-grafana-password-not-for-production}
export COMPOSE_PROJECT_NAME=${COMPOSE_PROJECT_NAME:-surendettement_ci_validation}
report_dir=${CI_REPORT_DIR:-app/reports/ci}
mkdir -p "$report_dir"

printf '%s\n' '1/8 Static checks'
python -m ruff check app assistant_api src web tests
python -m mypy \
  assistant_api/analytical_intents.py \
  assistant_api/sql_validation.py \
  assistant_api/sql_executor.py
python -m bandit -q -ll -r app assistant_api src web \
  -x '*/tests/*,*/test_*.py,*/migrations/*' \
  -s B112,B608

printf '%s\n' '2/8 Dependency audits'
python -m pip_audit -r requirements.txt
python -m pip_audit -r web/requirements.txt
python -m pip_audit -r assistant_api/requirements.txt

printf '%s\n' '3/8 Build application images'
docker compose --profile ci -f docker/compose.yaml build \
  api assistant-api django ci

printf '%s\n' '4/8 Unit, API, RAG and SQL tests'
docker compose --profile ci -f docker/compose.yaml run --rm --no-deps \
  -v "$(pwd)/$report_dir:/workspace/$report_dir" \
  ci python -m pytest -q tests app/tests -m 'not postgres_integration' \
  --junitxml="$report_dir/pytest.xml" \
  --cov=assistant_api --cov=app --cov=src \
  --cov-report="xml:$report_dir/coverage.xml"
docker compose --profile ci -f docker/compose.yaml run --rm --no-deps \
  -v "$(pwd)/$report_dir:/workspace/$report_dir" \
  ci python -m assistant_api.evaluation --offline \
  --output-dir "$report_dir/rag"
docker compose --profile ci -f docker/compose.yaml run --rm --no-deps \
  -v "$(pwd)/$report_dir:/workspace/$report_dir" \
  ci python -m benchmark.evaluation \
  --output-dir "$report_dir/text_to_sql"

printf '%s\n' '5/8 Django tests'
docker compose --profile ci -f docker/compose.yaml run --rm \
  -v "$(pwd)/$report_dir:/workspace/$report_dir" \
  ci python web/manage.py test \
  web.accounts web.dashboard web.assistant web.security \
  --testrunner=django.test.runner.DiscoverRunner

printf '%s\n' '6/8 PostgreSQL integration and migration validation'
CONFIRM_LOCAL_MIGRATION=yes sh docker/test_postgres_migration.sh

printf '%s\n' '7/8 Compose validation'
docker compose -f docker/compose.yaml config --quiet
docker compose -f docker/compose.yaml \
  -f docker/compose.production.yaml config --quiet
docker compose -f docker/compose.yaml \
  -f docker/compose.staging.yaml config --quiet

printf '%s\n' '8/8 Completed'
printf 'CI checks completed successfully.\n'
