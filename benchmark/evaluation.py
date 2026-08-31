"""Legacy-compatible deterministic evaluation for the Text-to-SQL dataset."""

from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

from assistant_api.sql_validation import SQLValidationError, validate_analytical_sql


REQUIRED_DATASET_FIELDS = {
    "schema_version", "dataset_version", "language", "allowed_views",
    "global_invariants", "offline_thresholds", "cases",
}
REQUIRED_CASE_FIELDS = {"id", "family", "question", "expected_action", "risk"}
EXPECTED_ACTIONS = {"execute", "deterministic", "refuse", "refuse_or_clarify"}


def evaluate_dataset(dataset: dict[str, Any]) -> dict[str, Any]:
    """Validate the legacy contract and every stored adversarial SQL."""
    contract_errors = _contract_errors(dataset)
    results = []
    reference_results = []
    for case in dataset.get("cases", []):
        if case.get("expected_action") == "execute":
            reference_results.append(_validate_reference_sql(case))
        sql = case.get("adversarial_sql")
        if not isinstance(sql, str) or not sql.strip():
            results.append({"id": case.get("id"), "evaluated": False, "passed": None})
            continue
        actual_reason = None
        try:
            validate_analytical_sql(sql)
        except SQLValidationError as exc:
            actual_reason = exc.code
        expected_reason = case.get("reason")
        blocked = actual_reason is not None
        results.append({
            "id": case.get("id"), "evaluated": True, "blocked": blocked,
            "expected_reason": expected_reason, "actual_reason": actual_reason,
            "passed": blocked and actual_reason == expected_reason,
        })

    evaluated = [result for result in results if result["evaluated"]]
    total = len(evaluated)
    metrics = {
        "schema_compliance": 0.0 if contract_errors else 1.0,
        "adversarial_block_rate": sum(bool(r["blocked"]) for r in evaluated) / total if total else 0.0,
        "refusal_reason_accuracy": sum(bool(r["passed"]) for r in evaluated) / total if total else 0.0,
        "reference_sql_compliance": (
            sum(bool(r["passed"]) for r in reference_results) / len(reference_results)
            if reference_results else 0.0
        ),
        "evaluated_sql_cases": total,
        "reference_sql_cases": len(reference_results),
        "dataset_cases": len(results),
    }
    thresholds = dataset.get("offline_thresholds", {})
    threshold_checks = {name: metrics.get(name, 0.0) >= threshold
                        for name, threshold in thresholds.items()}
    return {
        "evaluation_mode": "offline", "dataset_version": dataset.get("dataset_version"),
        "status": "PASS" if threshold_checks and all(threshold_checks.values()) else "FAIL",
        "contract_errors": contract_errors, "metrics": metrics,
        "thresholds": thresholds, "threshold_checks": threshold_checks,
        "results": results, "reference_results": reference_results,
    }


def evaluate_reference_results(
    dataset: dict[str, Any], execute: Callable[[str], list[dict[str, Any]]]
) -> list[dict[str, Any]]:
    """Execute legacy reference queries and compare their canonical rows."""
    results = []
    for case in dataset.get("cases", []):
        if case.get("expected_action") != "execute":
            continue
        actual = _canonical_rows(execute(case["reference_sql"]))
        expected = _canonical_rows(case["expected_rows"])
        results.append({"id": case["id"], "passed": actual == expected,
                        "expected_rows": expected, "actual_rows": actual})
    return results


def _validate_reference_sql(case: dict[str, Any]) -> dict[str, Any]:
    sql = case.get("reference_sql")
    expected_rows = case.get("expected_rows")
    if not isinstance(sql, str) or not sql.strip() or not isinstance(expected_rows, list):
        return {"id": case.get("id"), "passed": False, "reason": "oracle_missing"}
    try:
        validated = validate_analytical_sql(sql)
    except SQLValidationError as exc:
        return {"id": case.get("id"), "passed": False, "reason": exc.code}
    passed = case.get("expected_view") in validated.tables
    return {"id": case.get("id"), "passed": passed,
            "reason": None if passed else "expected_view_missing"}


def _canonical_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def scalar(value: Any) -> Any:
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, float):
            return round(value, 8)
        return value
    return [{key: scalar(value) for key, value in row.items()} for row in rows]


def _contract_errors(dataset: dict[str, Any]) -> list[str]:
    errors = []
    missing = sorted(REQUIRED_DATASET_FIELDS - dataset.keys())
    if missing:
        errors.append(f"missing_dataset_fields:{','.join(missing)}")
    cases = dataset.get("cases")
    if not isinstance(cases, list) or not cases:
        return [*errors, "cases_must_be_a_non_empty_list"]
    ids = []
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            errors.append(f"case_{index}_must_be_an_object")
            continue
        ids.append(case.get("id"))
        missing_case = sorted(REQUIRED_CASE_FIELDS - case.keys())
        if missing_case:
            errors.append(f"case_{index}_missing:{','.join(missing_case)}")
        if case.get("expected_action") not in EXPECTED_ACTIONS:
            errors.append(f"case_{index}_invalid_expected_action")
        if case.get("adversarial_sql") and not case.get("reason"):
            errors.append(f"case_{index}_adversarial_reason_required")
        if case.get("expected_action") == "execute" and (
            not case.get("reference_sql") or not isinstance(case.get("expected_rows"), list)
        ):
            errors.append(f"case_{index}_reference_oracle_required")
    if any(not isinstance(case_id, str) or not case_id for case_id in ids):
        errors.append("case_ids_must_be_non_empty_strings")
    if len(ids) != len(set(ids)):
        errors.append("case_ids_must_be_unique")
    thresholds = dataset.get("offline_thresholds")
    if not isinstance(thresholds, dict) or not thresholds:
        errors.append("offline_thresholds_must_be_a_non_empty_object")
    return errors


def write_reports(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "evaluation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    metrics = report["metrics"]
    failed = [result for result in report["results"] if result.get("passed") is False]
    lines = ["# Évaluation Text-to-SQL hors ligne", "", f"Statut : **{report['status']}**", "",
             f"- Dataset : `{report['dataset_version']}`",
             f"- Contrat conforme : {metrics['schema_compliance']:.0%}",
             f"- SQL adversariaux bloqués : {metrics['adversarial_block_rate']:.0%}",
             f"- Motifs de refus exacts : {metrics['refusal_reason_accuracy']:.0%}",
             f"- SQL de référence conformes : {metrics['reference_sql_compliance']:.0%}",
             f"- Cas SQL évalués : {metrics['evaluated_sql_cases']}/{metrics['dataset_cases']}",
             "", "## Échecs", ""]
    lines.extend(f"- `{r['id']}` : attendu `{r['expected_reason']}`, obtenu `{r['actual_reason']}`"
                 for r in failed)
    if not failed:
        lines.append("Aucun.")
    (output_dir / "evaluation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evaluate-text-to-sql")
    parser.add_argument("--dataset", type=Path,
                        default=Path("benchmark/text_to_sql_dataset.json"))
    parser.add_argument("--output-dir", type=Path,
                        default=Path("benchmark/reports/legacy"))
    args = parser.parse_args(argv)
    report = evaluate_dataset(json.loads(args.dataset.read_text(encoding="utf-8")))
    write_reports(report, args.output_dir)
    print(json.dumps({"status": report["status"], **report["metrics"]}))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
