"""Load and harmonise the single versioned benchmark dataset."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_DATASET = Path(__file__).with_name("text_to_sql_dataset.json")


def load_dataset(path: Path = DEFAULT_DATASET) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = [normalise_case(case) for case in data.get("cases", [])]
    ids = [case["id"] for case in cases]
    if not cases or len(ids) != len(set(ids)):
        raise ValueError("dataset cases must be non-empty and uniquely identified")
    return {**data, "cases": cases}


def normalise_case(case: dict[str, Any]) -> dict[str, Any]:
    """Map the legacy v1 vocabulary to the explicit benchmark contract."""
    legacy = case.get("expected_action")
    decision = {
        "execute": "execute",
        "deterministic": "execute",
        "refuse": "refuse",
        "refuse_or_clarify": "clarify",
    }.get(legacy, case.get("expected_decision"))
    if decision not in {"execute", "clarify", "refuse"}:
        raise ValueError(f"invalid expected decision for {case.get('id')}")
    risk = case.get("risk", "normal")
    return {
        **case,
        "expected_decision": decision,
        "oracle_sql": case.get("oracle_sql", case.get("reference_sql")),
        "expected_result": case.get("expected_result", case.get("expected_rows")),
        "expected_reason_category": case.get("expected_reason_category", case.get("reason", "valid")),
        "criticality": case.get("criticality", risk),
        "tags": case.get("tags", [case.get("family", "other"), risk]),
    }
