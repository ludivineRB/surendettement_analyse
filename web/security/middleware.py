"""Request identifiers and bounded local-recipe rate limits."""

from __future__ import annotations

from datetime import date
import logging
from time import monotonic
from uuid import UUID, uuid4

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse

logger = logging.getLogger("web.requests")


class RequestSecurityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started = monotonic()
        request.request_id = _request_id(request.headers.get("X-Request-ID"))
        refusal = self._rate_limit(request)
        response = refusal or self.get_response(request)
        response["X-Request-ID"] = request.request_id
        logger.info(
            "request_completed",
            extra={
                "request_id": request.request_id,
                "http_method": request.method,
                "http_path": request.path,
                "http_status": response.status_code,
                "duration_ms": round((monotonic() - started) * 1000),
                "actor_id": (
                    str(request.user.pk)
                    if getattr(request, "user", None) and request.user.is_authenticated
                    else None
                ),
            },
        )
        return response

    def _rate_limit(self, request):
        identity = (
            f"user:{request.user.pk}"
            if getattr(request, "user", None) and request.user.is_authenticated
            else f"ip:{_client_ip(request)}"
        )
        if not _consume(
            f"rate:general:{identity}",
            settings.RATE_LIMIT_REQUESTS,
            settings.RATE_LIMIT_WINDOW_SECONDS,
        ):
            return _too_many_requests("Trop de requêtes. Réessayez plus tard.")
        if request.method == "POST" and request.path == "/accounts/login/":
            if not _consume(
                f"rate:login:{_client_ip(request)}",
                settings.LOGIN_RATE_LIMIT_REQUESTS,
                settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS,
            ):
                return _too_many_requests("Trop de tentatives de connexion.")
        if request.method == "POST" and request.user.is_authenticated:
            quota = None
            kind = None
            if request.path.startswith("/assistant/informations/"):
                quota, kind = settings.INFORMATION_DAILY_QUOTA, "information"
            elif request.path.startswith("/assistant/sql/"):
                quota, kind = settings.SQL_DAILY_QUOTA, "sql"
            if quota is not None and not _consume(
                f"quota:{date.today().isoformat()}:{kind}:{request.user.pk}",
                quota,
                86_400,
            ):
                return _too_many_requests("Quota quotidien atteint.")
        return None


def _consume(key: str, limit: int, timeout: int) -> bool:
    if limit <= 0:
        return False
    if cache.add(key, 1, timeout=timeout):
        return True
    try:
        return cache.incr(key) <= limit
    except ValueError:
        cache.set(key, 1, timeout=timeout)
        return True


def _request_id(value: str | None) -> str:
    try:
        return str(UUID(value)) if value else str(uuid4())
    except ValueError:
        return str(uuid4())


def _client_ip(request) -> str:
    return request.META.get("REMOTE_ADDR", "unknown")


def _too_many_requests(message: str) -> HttpResponse:
    response = HttpResponse(message, status=429, content_type="text/plain")
    response["Retry-After"] = "60"
    return response
