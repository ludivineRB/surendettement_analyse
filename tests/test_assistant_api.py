import pytest
from fastapi import HTTPException

from assistant_api.main import answer_question, health
from assistant_api.schemas import AnswerRequest


def test_health_identifies_assistant_service():
    assert health() == {
        "status": "ok",
        "service": "assistant-api",
    }


def test_answer_refuses_to_invent_content_before_engines_are_ready():
    request = AnswerRequest(
        question="Quelle est la situation en France ?"
    )
    with pytest.raises(HTTPException) as error:
        answer_question(request)

    assert error.value.status_code == 503
    body = error.value.detail
    assert body["status"] == "not_ready"
    assert body["request_id"]
