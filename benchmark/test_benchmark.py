from pathlib import Path

import pytest

from benchmark.contracts import ContractError, parse_llm_response
from benchmark.dataset import load_dataset
from benchmark.fixture import initialise
from benchmark.llm_benchmark import evaluate, write_reports
from benchmark.providers import FixtureProvider
from benchmark.sql_guard import schema_from_sqlite, validate_sql


@pytest.fixture()
def db(tmp_path: Path) -> Path:
    return initialise(tmp_path / "fixture.db")


@pytest.mark.parametrize("payload,decision", [
    ({"decision": "execute", "sql": "SELECT 1", "reason": "ok", "clarification_question": None}, "execute"),
    ({"decision": "clarify", "sql": None, "reason": "ambiguous", "clarification_question": "Quelle période ?"}, "clarify"),
    ({"decision": "refuse", "sql": None, "reason": "unsafe", "clarification_question": None}, "refuse"),
])
def test_contract_valid(payload: dict, decision: str) -> None:
    assert parse_llm_response(payload).decision == decision


@pytest.mark.parametrize("payload", ["not json", {},
    {"decision": "execute", "sql": None, "reason": "x", "clarification_question": None},
    {"decision": "clarify", "sql": "SELECT 1", "reason": "x", "clarification_question": "x"},
])
def test_contract_rejects_malformed(payload: object) -> None:
    with pytest.raises(ContractError):
        parse_llm_response(payload)  # type: ignore[arg-type]


@pytest.mark.parametrize("sql,reason", [
    ("DELETE FROM analytics_risk_scores", "read_only_required"),
    ("SELECT score FROM analytics_risk_scores LIMIT 1; SELECT 1", "multiple_statements"),
    ("SELECT value FROM secret LIMIT 1", "table_forbidden"),
    ("SELECT secret FROM analytics_risk_scores LIMIT 1", "column_forbidden"),
    ("SELECT * FROM analytics_risk_scores LIMIT 1", "wildcard_forbidden"),
    ("SELECT a.score FROM analytics_risk_scores a JOIN analytics_risk_scores b ON a.score=b.score "
     "JOIN analytics_risk_scores c ON a.score=c.score JOIN analytics_risk_scores d ON a.score=d.score "
     "JOIN analytics_risk_scores e ON a.score=e.score LIMIT 1", "too_many_joins"),
    ("SELECT score FROM analytics_risk_scores LIMIT 201", "invalid_limit"),
    ("SELECT score FROM analytics_risk_scores", "limit_required"),
    ("SELECT pg_sleep(1) FROM analytics_risk_scores LIMIT 1", "function_forbidden"),
    ("SELECT score FROM analytics_risk_scores -- bypass\nLIMIT 1", "comment_forbidden"),
])
def test_guard_rejections(db: Path, sql: str, reason: str) -> None:
    assert validate_sql(sql, schema_from_sqlite(db)).reason_code == reason


@pytest.mark.parametrize("sql", [
    "WITH scores AS (SELECT score FROM analytics_risk_scores LIMIT 2) SELECT AVG(score) FROM scores",
    "SELECT score FROM analytics_risk_scores WHERE score > (SELECT AVG(score) FROM analytics_risk_scores) LIMIT 2",
])
def test_guard_accepts_cte_and_subquery(db: Path, sql: str) -> None:
    assert validate_sql(sql, schema_from_sqlite(db)).accepted


def test_fixture_metrics_and_reports(db: Path, tmp_path: Path) -> None:
    report = evaluate(FixtureProvider(), load_dataset(), db, 1)
    assert report["metrics"]["decision_accuracy"] == 1
    assert report["metrics"]["correct_treatment_rate"] == 1
    output = tmp_path / "reports"
    write_reports(report, output)
    assert (output / "evaluation.json").is_file()
    assert (output / "evaluation.md").is_file()


def test_dataset_contains_security_and_prompt_injection_cases() -> None:
    cases = load_dataset()["cases"]
    assert all({"id", "question", "expected_decision", "expected_reason_category",
                "criticality", "tags"} <= case.keys() for case in cases)
    assert any("prompt_injection" in case["tags"] for case in cases)
