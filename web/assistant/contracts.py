"""Runtime validation for responses from the Assistant API."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID


class AssistantResponseError(ValueError):
    """Raised when the Assistant API violates its public contract."""


def validate_answer(payload: Any) -> dict:
    if not isinstance(payload, Mapping):
        raise AssistantResponseError("answer response must be an object")
    required = {
        "answer",
        "sources",
        "data_references",
        "method",
        "request_id",
    }
    missing = required - payload.keys()
    if missing:
        raise AssistantResponseError(
            f"answer response is missing: {', '.join(sorted(missing))}"
        )
    if payload["method"] not in {"documents", "analytics", "hybrid"}:
        raise AssistantResponseError("answer method is invalid")
    if not isinstance(payload["answer"], str) or not payload["answer"].strip():
        raise AssistantResponseError("answer text is empty")
    if not isinstance(payload["sources"], list):
        raise AssistantResponseError("answer sources must be a list")
    if not isinstance(payload["data_references"], list):
        raise AssistantResponseError("data references must be a list")
    try:
        UUID(str(payload["request_id"]))
    except ValueError as exc:
        raise AssistantResponseError("request_id is invalid") from exc
    return dict(payload)
