#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
  printf 'Usage: CONFIRM_RESTORE_TEST=yes sh docker/test_restore_postgres.sh BACKUP.dump\n' >&2
  exit 2
fi
if [ "${CONFIRM_RESTORE_TEST:-no}" != "yes" ]; then
  printf 'Restore test refused: set CONFIRM_RESTORE_TEST=yes.\n' >&2
  exit 2
fi

backup=$1
test -f "$backup"
test -s "$backup"

env_file=${ENV_FILE:-./.env}
set -a
. "$env_file"
set +a
database=${POSTGRES_DB:-surendettement}
user=${POSTGRES_USER:-surendettement}
temporary_database="restore_validation_$$"

compose() {
  docker compose --env-file "$env_file" \
    -f docker/compose.yaml -f docker/compose.staging.yaml "$@"
}

cleanup() {
  compose exec -T postgres psql --username "$user" --dbname "$database" \
    --set=ON_ERROR_STOP=1 \
    --command "DROP DATABASE IF EXISTS $temporary_database WITH (FORCE)" >/dev/null
}
trap cleanup EXIT INT TERM

compose exec -T postgres psql --username "$user" --dbname "$database" \
  --set=ON_ERROR_STOP=1 \
  --command "CREATE DATABASE $temporary_database"
compose exec -T postgres pg_restore --exit-on-error --no-owner --no-privileges \
  --username "$user" --dbname "$temporary_database" < "$backup"
compose exec -T postgres psql --username "$user" --dbname "$temporary_database" \
  --set=ON_ERROR_STOP=1 \
  --command "SELECT COUNT(*) AS migrations FROM schema_migrations" \
  --command "SELECT COUNT(*) AS scores FROM risk_scores"

printf 'Restore validation succeeded in temporary database %s.\n' "$temporary_database"
