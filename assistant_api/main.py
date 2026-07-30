"""HTTP entry point for the standalone business assistant."""

from uuid import uuid4

from fastapi import FastAPI, HTTPException

from assistant_api.schemas import AnswerRequest


app = FastAPI(
    title="Surendettement Business Assistant API",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "assistant-api"}


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
