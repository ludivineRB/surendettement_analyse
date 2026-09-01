"""HTTP entry point for the standalone business assistant."""

import os
import json
import logging
from collections import Counter
from time import monotonic
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from assistant_api.repository import search_active_chunks
from assistant_api.auth import get_internal_token, require_internal_token
from assistant_api.analytics import AnalyticsClient, AnalyticsUnavailable
from assistant_api.conversation_routing import classify_question
from assistant_api.generation import (
    GeneratorUnavailable,
    InsufficientGrounding,
    TextGenerator,
    generate_grounded_answer,
)
from assistant_api.orchestration import GroundingContext, build_grounding_context
from assistant_api.openai_provider import get_text_generator
from assistant_api.schemas import (
    AnswerRequest,
    AnswerResponse,
    DataReference,
    RetrievalRequest,
    RetrievalResponse,
    SourceReference,
)
from assistant_api.storage import get_engine
from assistant_api.sql_service import SQLClarificationRequired, run_text_to_sql
from assistant_api.monitoring import metrics as prometheus


app = FastAPI(
    title="Surendettement Business Assistant API",
    version="0.1.0",
)
logger = logging.getLogger("assistant.requests")
_metrics = Counter()


@app.middleware("http")
async def operational_metrics(request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    started = monotonic()
    _metrics["requests_in_progress"] += 1
    try:
        response = await call_next(request)
        status = response.status_code
    except Exception:
        status = 500
        raise
    finally:
        duration_ms = round((monotonic() - started) * 1000)
        _metrics["requests_in_progress"] -= 1
        _metrics["requests_total"] += 1
        _metrics[f"responses_{status}"] += 1
        _metrics["duration_ms_total"] += duration_ms
        labels = {"method": request.method, "path": request.url.path, "status": str(status)}
        prometheus.increment("assistant_http_requests_total", **labels)
        prometheus.observe("assistant_http_request_duration_seconds", duration_ms / 1000, **labels)
        logger.info(
            json.dumps(
                {
                    "message": "request_completed",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": status,
                    "duration_ms": duration_ms,
                },
                ensure_ascii=False,
            )
        )
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "assistant-api"}


@app.get("/health/live", include_in_schema=False)
def live() -> dict[str, str]:
    return health()


@app.get("/health/ready", include_in_schema=False)
def ready(engine: Engine = Depends(get_engine)):
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="assistant database unavailable") from exc
    return {"status": "ok", "database": "ok"}


@app.get("/metrics")
def metrics() -> dict[str, int]:
    return dict(_metrics)


@app.get("/metrics/prometheus", response_class=PlainTextResponse, include_in_schema=False)
def prometheus_metrics() -> str:
    return prometheus.render()


@app.post("/v1/retrieval/search", response_model=RetrievalResponse)
def retrieval_search(
    request: RetrievalRequest,
    engine: Engine = Depends(get_engine),
) -> RetrievalResponse:
    try:
        results = search_active_chunks(
            engine,
            request.query,
            limit=request.limit,
        )
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="Le corpus documentaire est indisponible.",
        ) from exc
    return RetrievalResponse(query=request.query, results=results)


@app.post(
    "/v1/answers",
    response_model=AnswerResponse,
    responses={503: {"description": "Assistant engines are not configured"}},
)
def answer_question(
    request: AnswerRequest,
    engine: Engine = Depends(get_engine),
    analytics_client: AnalyticsClient = Depends(AnalyticsClient),
    generator: TextGenerator = Depends(get_text_generator),
    x_internal_token: str | None = Depends(get_internal_token),
) -> AnswerResponse:
    request_id = uuid4()
    category = classify_question(request.question, request.mode)
    if category in {"unsupported", "sensitive_or_individual_request"}:
        answer = (
            "Je ne peux pas produire de diagnostic ou de conseil individuel. "
            "Je peux uniquement présenter des informations statistiques territoriales."
            if category == "sensitive_or_individual_request"
            else "Cette demande est trop large ou ne correspond pas aux analyses autorisées."
        )
        return AnswerResponse(
            answer=answer,
            sources=[],
            data_references=[],
            method="refusal",
            category=category,
            request_id=request_id,
        )
    if category == "advanced_sql":
        require_internal_token(x_internal_token)
        try:
            sql_result = run_text_to_sql(
                request.question,
                generator=generator,
                audit_engine=engine,
                request_id=request_id,
                actor_id=request.actor_id,
                model_version=os.getenv("OPENAI_MODEL", "unknown"),
            )
            context = GroundingContext(
                method="advanced_sql",
                documentary_chunks=[],
                analytics_dataset=None,
                analytics_rows=sql_result.sql_execution.rows,
                analytical_sql=sql_result.sql_execution.validated.sql,
            )
        except SQLClarificationRequired as exc:
            return AnswerResponse(
                answer=str(exc),
                sources=[],
                data_references=[],
                method="refusal",
                category=category,
                request_id=request_id,
            )
        except Exception as exc:
            if isinstance(exc, HTTPException):
                raise
            raise HTTPException(status_code=503, detail="Analyse SQL indisponible.") from exc
        row_count = len(sql_result.sql_execution.rows)
        if row_count == 0:
            answer = (
                "La requête en lecture seule a été exécutée correctement, "
                "mais aucune donnée ne correspond aux critères demandés. "
                "Vous pouvez élargir la période, le territoire ou "
                "l’indicateur recherché."
            )
        else:
            try:
                answer = generate_grounded_answer(request.question, context, generator)
            except Exception:
                logger.exception(
                    "SQL answer synthesis failed after successful execution",
                    extra={
                        "request_id": str(request_id),
                        "sql_execution_id": str(sql_result.execution_id),
                        "row_count": row_count,
                    },
                )
                answer = (
                    "La requête en lecture seule a été exécutée avec succès "
                    f"et a retourné {row_count} ligne(s). La synthèse textuelle "
                    "est temporairement indisponible ; consultez le SQL généré "
                    "et les résultats ci-dessous."
                )
        return AnswerResponse(
            answer=answer,
            sources=[],
            data_references=[],
            method="advanced_sql",
            category=category,
            result_rows=sql_result.sql_execution.rows,
            generated_sql=sql_result.sql_execution.validated.sql,
            sql_execution_id=sql_result.execution_id,
            request_id=request_id,
        )
    try:
        context = build_grounding_context(
            request.question,
            engine=engine,
            analytics_client=analytics_client,
        )
        answer = generate_grounded_answer(
            request.question,
            context,
            generator,
        )
    except InsufficientGrounding:
        return AnswerResponse(
            answer=(
                "Les sources approuvées disponibles ne permettent pas de "
                "répondre à cette question de façon fiable."
            ),
            sources=[],
            data_references=[],
            method="refusal",
            category=category,
            request_id=request_id,
        )
    except (AnalyticsUnavailable, GeneratorUnavailable, SQLAlchemyError) as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "not_ready",
                "detail": str(exc),
                "request_id": str(request_id),
            },
        ) from exc
    sources = [
        SourceReference(
            title=chunk["source_title"],
            url=chunk["source_url"],
            publisher=chunk["publisher"],
            reference_period=chunk["reference_period"],
        )
        for chunk in context.documentary_chunks
    ]
    data_references = [
        DataReference(
            indicator_code=str(
                row.get("indicator_code")
                or (
                    context.analytical_intent.metric
                    if context.analytical_intent
                    else "unknown"
                )
            ),
            territory=str(
                row.get("departement_name")
                or row.get("region_name")
                or row.get("geographic_name")
                or row.get("geographic_code")
                or "France"
            ),
            reference_period=str(
                row.get("reference_period")
                or row.get("reference_year")
                or "unknown"
            ),
        )
        for row in context.analytics_rows[:100]
    ]
    return AnswerResponse(
        answer=answer,
        sources=sources,
        data_references=data_references,
        method=context.method,
        category=category,
        interpreted_filters=(
            context.analytical_intent.model_dump(mode="json", exclude_none=True)
            if context.analytical_intent
            else {}
        ),
        result_rows=context.analytics_rows[:100],
        request_id=request_id,
    )
