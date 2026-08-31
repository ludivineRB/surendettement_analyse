"""Strict response contract shared by every Text-to-SQL provider."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Any


DECISIONS = {"execute", "clarify", "refuse"}


class ContractError(ValueError):
    """Raised when a provider response cannot be used safely."""


@dataclass(frozen=True)
class LLMDecision:
    decision: str
    sql: str | None
    reason: str
    clarification_question: str | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_llm_response(payload: str | dict[str, Any]) -> LLMDecision:
    """Parse JSON without attempting to recover SQL from free-form text."""
    if isinstance(payload, str):
        try:
            value = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ContractError("invalid_json") from exc
    else:
        value = payload
    if not isinstance(value, dict):
        raise ContractError("response_must_be_an_object")
    expected = {"decision", "sql", "reason", "clarification_question"}
    if set(value) != expected:
        raise ContractError("invalid_fields")
    decision = value["decision"]
    sql = value["sql"]
    reason = value["reason"]
    question = value["clarification_question"]
    if decision not in DECISIONS:
        raise ContractError("invalid_decision")
    if not isinstance(reason, str) or not reason.strip():
        raise ContractError("reason_required")
    if decision == "execute":
        if not isinstance(sql, str) or not sql.strip() or question is not None:
            raise ContractError("invalid_execute_contract")
    elif decision == "clarify":
        if sql is not None or not isinstance(question, str) or not question.strip():
            raise ContractError("invalid_clarify_contract")
    elif sql is not None or question is not None:
        raise ContractError("invalid_refuse_contract")
    return LLMDecision(decision, sql.strip() if isinstance(sql, str) else None, reason.strip(), question)
