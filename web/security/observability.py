"""Django health probes and process-local Prometheus metrics."""

from __future__ import annotations

from collections import Counter
from threading import Lock
from time import monotonic

from django.http import JsonResponse, HttpResponse

_values: Counter[tuple[str, tuple[tuple[str, str], ...]]] = Counter()
_lock = Lock()


def record_request(method: str, path: str, status: int, duration: float) -> None:
    labels = tuple(sorted({"method": method, "path": path, "status": str(status)}.items()))
    with _lock:
        _values[("django_http_requests_total", labels)] += 1
        _values[("django_http_request_duration_seconds_count", labels)] += 1
        _values[("django_http_request_duration_seconds_sum", labels)] += duration


def live(_request):
    return JsonResponse({"status": "ok", "service": "django"})


def ready(_request):
    from django.db import connection

    started = monotonic()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return JsonResponse({"status": "not_ready", "database": "error"}, status=503)
    return JsonResponse(
        {"status": "ok", "database": "ok", "duration_ms": round((monotonic() - started) * 1000)}
    )


def prometheus_metrics(_request):
    with _lock:
        values = sorted(_values.items())
    lines = []
    for (name, labels), value in values:
        suffix = "{" + ",".join(f'{key}="{val}"' for key, val in labels) + "}"
        lines.append(f"{name}{suffix} {value}")
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain; version=0.0.4")
