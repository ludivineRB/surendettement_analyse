import json
import logging
from time import monotonic
from uuid import uuid4

from fastapi import FastAPI, Response

from app.core.config import settings
from app.core.monitoring import metrics
from app.views.analytics_api import analytics_api
from app.views.risk_scores_api import risk_scores_api


app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)
logger = logging.getLogger("app.requests")
app.include_router(analytics_api)
app.include_router(risk_scores_api)


@app.middleware("http")
async def observe_requests(request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    started = monotonic()
    try:
        response = await call_next(request)
        status = response.status_code
    except Exception:
        status = 500
        raise
    finally:
        duration = monotonic() - started
        labels = {"method": request.method, "path": request.url.path, "status": str(status)}
        metrics.increment("fastapi_http_requests_total", **labels)
        metrics.observe("fastapi_http_request_duration_seconds", duration, **labels)
        logger.info(json.dumps({"message": "request_completed", "request_id": request_id,
                                "method": request.method, "path": request.url.path,
                                "status": status, "duration_ms": round(duration * 1000)}))
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/")
async def root() -> dict:
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/api/data/health",
    }


@app.get("/health/live", include_in_schema=False)
def live() -> dict:
    return {"status": "ok", "service": "api"}


@app.get("/metrics", include_in_schema=False)
def prometheus_metrics() -> Response:
    return Response(metrics.render(), media_type="text/plain; version=0.0.4")
