#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
  printf 'Usage: CONFIRM_RESTORE=yes sh docker/restore_postgres.sh BACKUP.dump\n' >&2
  exit 2
fi
if [ "${CONFIRM_RESTORE:-no}" != "yes" ]; then
  printf 'Restore refused: set CONFIRM_RESTORE=yes after checking the target.\n' >&2
  exit 2
fi

backup=$1
env_file=${ENV_FILE:-./.env}
set -a
. "$env_file"
set +a
database=${POSTGRES_DB:-surendettement}
user=${POSTGRES_USER:-surendettement}

test -f "$backup"
test -s "$backup"
docker compose --env-file "$env_file" \
  -f docker/compose.yaml -f docker/compose.staging.yaml exec -T postgres \
  pg_restore --clean --if-exists --no-owner --no-privileges \
  --exit-on-error --username "$user" --dbname "$database" < "$backup"

printf 'Restore completed from %s\n' "$backup"
