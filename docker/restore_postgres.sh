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
database=${POSTGRES_DB:-surendettement}
user=${POSTGRES_USER:-surendettement}

test -f "$backup"
test -s "$backup"
docker compose -f docker/compose.yaml exec -T postgres \
  pg_restore --clean --if-exists --no-owner --no-privileges \
  --exit-on-error --username "$user" --dbname "$database" < "$backup"

printf 'Restore completed from %s\n' "$backup"
