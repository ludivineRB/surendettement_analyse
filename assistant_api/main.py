"""HTTP entry point for the standalone business assistant."""

from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from assistant_api.repository import search_active_chunks
from assistant_api.analytics import AnalyticsClient, AnalyticsUnavailable
from assistant_api.generation import (
    GeneratorUnavailable,
    InsufficientGrounding,
    TextGenerator,
    UnconfiguredGenerator,
    generate_grounded_answer,
)
from assistant_api.orchestration import build_grounding_context
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


app = FastAPI(
    title="Surendettement Business Assistant API",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "assistant-api"}


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
) -> AnswerResponse:
    request_id = uuid4()
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
    except (
        AnalyticsUnavailable,
        GeneratorUnavailable,
        InsufficientGrounding,
        SQLAlchemyError,
    ) as exc:
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
            indicator_code=str(row.get("indicator_code", "unknown")),
            territory=str(
                row.get("departement_name")
                or row.get("region_name")
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
        request_id=request_id,
    )
