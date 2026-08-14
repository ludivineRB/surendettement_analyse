"""HTTP entry point for the standalone business assistant."""

from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from assistant_api.repository import search_active_chunks
from assistant_api.schemas import (
    AnswerRequest,
    RetrievalRequest,
    RetrievalResponse,
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
    responses={503: {"description": "Assistant engines are not configured"}},
)
def answer_question(request: AnswerRequest) -> None:
    request_id = uuid4()
    raise HTTPException(
        status_code=503,
        detail={
            "status": "not_ready",
            "detail": (
                "Le corpus métier et le connecteur analytique "
                "ne sont pas encore configurés."
            ),
            "request_id": str(request_id),
        },
    )
