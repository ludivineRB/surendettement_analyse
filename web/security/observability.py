"""Django health probes and process-local Prometheus metrics."""

from __future__ import annotations

from collections import Counter
from threading import Lock
from time import monotonic

from django.db import DatabaseError
from django.db.models import Count
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
    lines.extend(_assistant_feedback_metrics())
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain; version=0.0.4")


def _assistant_feedback_metrics() -> list[str]:
    """Return durable, low-cardinality assistant feedback counters from the DB."""
    from web.assistant.models import Conversation, ConversationMessage

    counts = {
        (kind, feedback): 0
        for kind in (Conversation.Kind.INFORMATION, Conversation.Kind.SQL)
        for feedback in ("useful", "not_useful")
    }
    try:
        rows = (
            ConversationMessage.objects.filter(
                role=ConversationMessage.Role.ASSISTANT,
                feedback__in=("useful", "not_useful"),
            )
            .values("conversation__kind", "feedback")
            .annotate(total=Count("id"))
        )
        for row in rows:
            counts[(row["conversation__kind"], row["feedback"])] = row["total"]
    except DatabaseError:
        return ["django_assistant_feedback_collection_available 0"]

    lines = ["django_assistant_feedback_collection_available 1"]
    lines.extend(
        f'django_assistant_feedback_total{{kind="{kind}",feedback="{feedback}"}} {total}'
        for (kind, feedback), total in sorted(counts.items())
    )
    return lines
