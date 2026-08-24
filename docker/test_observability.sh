#!/bin/sh
set -eu

compose_file=${COMPOSE_FILE:-docker/compose.yaml}
project=${COMPOSE_PROJECT_NAME:-surendettement_staging_validation}
monitoring_dir=$(pwd)/docker/monitoring

printf '%s\n' '1/4 Validate Prometheus rules and alert scenarios'
docker run --rm -v "$monitoring_dir:/monitoring:ro" \
  --entrypoint promtool prom/prometheus:v3.5.0 \
  check rules /monitoring/alerts.yml
docker run --rm -v "$monitoring_dir:/monitoring:ro" \
  --entrypoint promtool prom/prometheus:v3.5.0 \
  test rules /monitoring/alerts.test.yml

printf '%s\n' '2/4 Check service metrics from the Docker network'
docker compose -p "$project" -f "$compose_file" exec -T api python -c \
  "import urllib.request; urls=('http://api:8020/metrics','http://assistant-api:8030/metrics/prometheus','http://django:8000/metrics/'); [print(url, urllib.request.urlopen(url, timeout=5).status) for url in urls]"

printf '%s\n' '3/4 Check Prometheus targets and Grafana health'
docker compose -p "$project" -f "$compose_file" exec -T api python -c \
  "import json,urllib.request; targets=json.load(urllib.request.urlopen('http://prometheus:9090/api/v1/targets',timeout=5))['data']['activeTargets']; assert targets and all(item['health']=='up' for item in targets), targets; print('Prometheus targets: UP'); print('Grafana:',json.load(urllib.request.urlopen('http://grafana:3000/api/health',timeout=5))['database'])"

if [ "${1:-}" = "--demo-django-outage" ]; then
  printf '%s\n' '4/4 Demonstrate a controlled Django outage (150 seconds)'
  docker compose -p "$project" -f "$compose_file" stop django
  trap 'docker compose -p "$project" -f "$compose_file" start django' EXIT INT TERM
  sleep 150
  docker compose -p "$project" -f "$compose_file" start django
  trap - EXIT INT TERM
  printf '%s\n' 'Django restarted; ServiceUnavailable remains visible until resolution.'
else
  printf '%s\n' '4/4 Destructive demo skipped (use --demo-django-outage in staging)'
fi

printf '%s\n' 'Observability validation completed successfully.'
