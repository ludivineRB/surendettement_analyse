"""Small Text-to-SQL decoding-strategy POC with no database execution."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import Any, Callable

from assistant_api.generation import TextGenerator
from assistant_api.openai_provider import OpenAIResponsesGenerator
from assistant_api.sql_generation import (
    ANALYTICS_SCHEMA,
    ANALYTICS_SEMANTICS,
    generate_sql_candidate,
)
from assistant_api.sql_service import require_specific_question
from assistant_api.sql_validation import validate_analytical_sql


DEFAULT_CASE_IDS = {
    "quality_aggregate_01",
    "quality_ranking_01",
    "quality_territory_01",
    "ambiguous_01",
    "nonexistent_column_01",
    "injection_01",
}


@dataclass(frozen=True)
class DecodedSQL:
    sql: str
    calls: int
    input_tokens: int
    output_tokens: int


class ReferenceGenerator:
    """Free plumbing check; it is not an experimental model result."""

    def __init__(self, references: dict[str, str]) -> None:
        self.references = references
        self.last_usage: dict[str, int] = {}

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        payload = json.loads(user_prompt)
        if "candidate_sql" in payload:
            return json.dumps({"sql": payload["candidate_sql"]})
        question = payload["question"]
        sql = self.references.get(question, "SELECT unknown_column FROM analytics_risk_scores LIMIT 1")
        return json.dumps({"sql": sql})


def run_poc(
    dataset: dict[str, Any],
    generator: TextGenerator,
    *,
    strategy_names: list[str],
    case_ids: set[str] = DEFAULT_CASE_IDS,
) -> dict[str, Any]:
    cases = [case for case in dataset["cases"] if case["id"] in case_ids]
    rows = []
    for strategy_name in strategy_names:
        decoder = STRATEGIES[strategy_name]
        for case in cases:
            started = monotonic()
            actual_action = "execute"
            reason = None
            decoded = DecodedSQL("", 0, 0, 0)
            tables: list[str] = []
            try:
                require_specific_question(case["question"])
                decoded = decoder(case["question"], generator)
                tables = sorted(validate_analytical_sql(decoded.sql).tables)
            except Exception as exc:
                actual_action = "refuse"
                reason = getattr(exc, "code", type(exc).__name__)
            expected = case["expected_action"]
            passed = (
                expected == "execute"
                and actual_action == "execute"
                and case.get("expected_view") in tables
            ) or (
                expected in {"refuse", "refuse_or_clarify"}
                and actual_action == "refuse"
            )
            rows.append(
                {
                    "strategy": strategy_name,
                    "case_id": case["id"],
                    "expected_action": expected,
                    "actual_action": actual_action,
                    "reason": reason,
                    "passed": passed,
                    "calls": decoded.calls,
                    "input_tokens": decoded.input_tokens,
                    "output_tokens": decoded.output_tokens,
                    "latency_ms": round((monotonic() - started) * 1_000, 3),
                }
            )
    summary = []
    for name in strategy_names:
        selected = [row for row in rows if row["strategy"] == name]
        summary.append(
            {
                "strategy": name,
                "cases": len(selected),
                "pass_rate": sum(bool(row["passed"]) for row in selected) / len(selected),
                "calls": sum(int(row["calls"]) for row in selected),
                "input_tokens": sum(int(row["input_tokens"]) for row in selected),
                "output_tokens": sum(int(row["output_tokens"]) for row in selected),
                "latency_ms": round(sum(float(row["latency_ms"]) for row in selected), 3),
            }
        )
    return {
        "poc_version": "1.0",
        "dataset_version": dataset.get("dataset_version"),
        "database_execution": False,
        "mode": "reference" if isinstance(generator, ReferenceGenerator) else "live",
        "summary": summary,
        "results": rows,
    }


def _current(question: str, generator: TextGenerator) -> DecodedSQL:
    sql = generate_sql_candidate(question, generator)
    input_tokens, output_tokens = _usage(generator)
    return DecodedSQL(sql, 1, input_tokens, output_tokens)


def _schema_only(question: str, generator: TextGenerator) -> DecodedSQL:
    return _single_prompt(question, generator, views=ANALYTICS_SCHEMA)


def _few_shot(question: str, generator: TextGenerator) -> DecodedSQL:
    examples = [
        {
            "question": "Classe les départements par score en 2025.",
            "sql": "SELECT geographic_code, score FROM analytics_risk_scores "
            "WHERE geographic_level = 'department' AND reference_period = '2025' "
            "ORDER BY score DESC LIMIT 10",
        },
        {
            "question": "Quel est le score moyen des régions en 2025 ?",
            "sql": "SELECT AVG(score) AS average_score FROM analytics_risk_scores "
            "WHERE geographic_level = 'region' AND reference_period = '2025' LIMIT 1",
        },
    ]
    return _single_prompt(
        question,
        generator,
        views=ANALYTICS_SCHEMA,
        extras={"examples": examples},
    )


def _retrieval(question: str, generator: TextGenerator) -> DecodedSQL:
    normalized = question.casefold()
    selected = {
        name: columns
        for name, columns in ANALYTICS_SCHEMA.items()
        if _view_relevant(name, normalized)
    }
    if not selected:
        selected = {"analytics_risk_scores": ANALYTICS_SCHEMA["analytics_risk_scores"]}
    return _single_prompt(question, generator, views=selected)


def _review(question: str, generator: TextGenerator) -> DecodedSQL:
    first = _single_prompt(question, generator, views=ANALYTICS_SCHEMA)
    response = generator.generate(
        system_prompt=(
            "Vérifie et corrige ce SQL PostgreSQL. Utilise seulement le schéma fourni "
            "et retourne uniquement {\"sql\": \"SELECT ... LIMIT n\"}."
        ),
        user_prompt=json.dumps(
            {
                "question": question,
                "candidate_sql": first.sql,
                "views": ANALYTICS_SCHEMA,
            },
            ensure_ascii=False,
        ),
    )
    input_tokens, output_tokens = _usage(generator)
    return DecodedSQL(
        _extract_sql(response),
        2,
        first.input_tokens + input_tokens,
        first.output_tokens + output_tokens,
    )


STRATEGIES: dict[str, Callable[[str, TextGenerator], DecodedSQL]] = {
    "current": _current,
    "schema_only": _schema_only,
    "few_shot": _few_shot,
    "retrieval": _retrieval,
    "review": _review,
}


def _single_prompt(
    question: str,
    generator: TextGenerator,
    *,
    views: dict[str, list[str]],
    extras: dict[str, Any] | None = None,
) -> DecodedSQL:
    payload = {
        "question": question,
        "views": views,
        "semantics": ANALYTICS_SEMANTICS,
        **(extras or {}),
    }
    response = generator.generate(
        system_prompt=(
            "Traduis la question en une seule requête SELECT PostgreSQL. "
            "Utilise uniquement les vues et colonnes fournies, sans commentaire ni joker. "
            "Retourne uniquement un objet JSON {\"sql\": \"SELECT ... LIMIT n\"}."
        ),
        user_prompt=json.dumps(payload, ensure_ascii=False),
    )
    input_tokens, output_tokens = _usage(generator)
    return DecodedSQL(_extract_sql(response), 1, input_tokens, output_tokens)


def _extract_sql(response: str) -> str:
    payload = json.loads(response)
    if set(payload) != {"sql"} or not isinstance(payload["sql"], str):
        raise ValueError("invalid_generation_contract")
    return payload["sql"].strip()


def _usage(generator: TextGenerator) -> tuple[int, int]:
    usage = getattr(generator, "last_usage", {})
    if not isinstance(usage, dict):
        return 0, 0
    return int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0))


def _view_relevant(view: str, question: str) -> bool:
    rules = {
        "analytics_risk_scores": ("score", "risque"),
        "analytics_score_factors": ("facteur", "contribution", "explique"),
        "analytics_observations": ("observation", "variation"),
        "analytics_model_comparisons": ("modèle", "modele", "version"),
        "analytics_macro_regions": ("chômage", "chomage", "population", "famille"),
        "analytics_pipeline_status": ("fraîcheur", "fraicheur", "pipeline"),
    }
    return any(term in question for term in rules[view])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="text-to-sql-decoding-poc")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-paid-calls", action="store_true")
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-5.6-terra"))
    parser.add_argument("--strategies", nargs="+", choices=sorted(STRATEGIES), default=list(STRATEGIES))
    parser.add_argument("--dataset", type=Path, default=Path("benchmark/text_to_sql_dataset.json"))
    parser.add_argument("--output", type=Path, default=Path("benchmark/poc_report.json"))
    args = parser.parse_args(argv)
    if args.live and not args.confirm_paid_calls:
        parser.error("--confirm-paid-calls is required with --live")
    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    references = {
        case["question"]: case["reference_sql"]
        for case in dataset["cases"]
        if case.get("reference_sql")
    }
    generator: TextGenerator = (
        OpenAIResponsesGenerator(api_key=os.getenv("OPENAI_API_KEY", ""), model=args.model)
        if args.live
        else ReferenceGenerator(references)
    )
    report = run_poc(dataset, generator, strategy_names=args.strategies)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
