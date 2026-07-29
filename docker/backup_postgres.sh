#!/bin/sh
set -eu

backup_dir=${BACKUP_DIR:-./backups}
database=${POSTGRES_DB:-surendettement}
user=${POSTGRES_USER:-surendettement}
timestamp=$(date -u +%Y%m%dT%H%M%SZ)
destination="${backup_dir}/${database}_${timestamp}.dump"

mkdir -p "$backup_dir"
umask 077
docker compose -f docker/compose.yaml exec -T postgres \
  pg_dump --format=custom --no-owner --no-privileges \
  --username "$user" --dbname "$database" > "$destination"

test -s "$destination"
printf '%s\n' "$destination"
