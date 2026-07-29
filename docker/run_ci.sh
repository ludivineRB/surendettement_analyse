#!/bin/sh
set -eu

export POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-ci-ephemeral-password}

docker compose -f docker/compose.yaml build api
docker compose -f docker/compose.yaml run --rm --no-deps \
  api python -m pytest -q
docker compose -f docker/compose.yaml config --quiet
docker compose -f docker/compose.yaml \
  -f docker/compose.production.yaml config --quiet

printf 'CI checks completed successfully.\n'
