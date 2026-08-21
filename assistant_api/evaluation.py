"""Versioned black-box evaluation for the information assistant."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any, Callable
from urllib import error, request
from urllib.parse import urlparse

from assistant_api.conversation_routing import classify_question
from assistant_api.routing import route_question


Transport = Callable[[str], dict[str, Any]]
_REQUIRED_CASE_FIELDS = {
    "id",
    "family",
    "question",
    "expected_category",
    "expected_methods",
    "evidence_required",
    "allowed_publishers",
}


def evaluate_case(case: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    sources = response.get("sources") or []
    data_references = response.get("data_references") or []
    publishers = {source.get("publisher") for source in sources}
    allowed = set(case.get("allowed_publishers") or [])
    required = set(case.get("required_publishers") or [])
    checks = {
        "category": response.get("category") == case["expected_category"],
        "method": response.get("method") in case["expected_methods"],
        "refusal": (
            response.get("method") == "refusal"
            if case.get("refusal_required")
            else True
        ),
        "evidence": (
            bool(sources or data_references)
            if case.get("evidence_required")
            else True
        ),
        "publishers": not publishers - allowed if allowed else not publishers,
        "required_publishers": required <= publishers,
        "no_information_sql": response.get("generated_sql") is None,
    }
    return {
        "id": case["id"],
        "family": case["family"],
        "checks": checks,
        "passed": all(checks.values()),
        "actual_category": response.get("category"),
        "actual_method": response.get("method"),
        "source_publishers": sorted(value for value in publishers if value),
    }


def evaluate_dataset(dataset: dict[str, Any], transport: Transport) -> dict[str, Any]:
    results = []
    for case in dataset["cases"]:
        started = time.monotonic()
        try:
            response = transport(case["question"])
            result = evaluate_case(case, response)
            result["available"] = True
        except Exception as exc:
            result = {
                "id": case["id"],
                "family": case["family"],
                "checks": {},
                "passed": False,
                "available": False,
                "error": type(exc).__name__,
            }
        result["duration_ms"] = round((time.monotonic() - started) * 1000)
        results.append(result)

    total = len(results)
    available = [result for result in results if result["available"]]
    refusals = [
        result
        for case, result in zip(dataset["cases"], results)
        if case.get("refusal_required")
    ]

    def rate(check: str, population: list[dict[str, Any]] = available) -> float:
        if not population:
            return 0.0
        return sum(bool(item.get("checks", {}).get(check)) for item in population) / len(population)

    metrics = {
        "availability": len(available) / total if total else 0.0,
        "category_accuracy": rate("category"),
        "method_accuracy": rate("method"),
        "refusal_recall": rate("refusal", refusals),
        "evidence_compliance": rate("evidence"),
        "publisher_compliance": rate("publishers"),
        "required_publisher_compliance": rate("required_publishers"),
        "passed_cases": sum(result["passed"] for result in results),
        "total_cases": total,
    }
    metrics["case_pass_rate"] = (
        metrics["passed_cases"] / total if total else 0.0
    )
    thresholds = dataset["thresholds"]
    threshold_checks = {
        name: metrics[name] >= threshold for name, threshold in thresholds.items()
    }
    return {
        "dataset_version": dataset["dataset_version"],
        "status": "PASS" if all(threshold_checks.values()) else "FAIL",
        "metrics": metrics,
        "thresholds": thresholds,
        "threshold_checks": threshold_checks,
        "results": results,
    }


def evaluate_offline_dataset(dataset: dict[str, Any]) -> dict[str, Any]:
    """Evaluate deterministic contracts without services or model credentials."""
    cases = dataset.get("cases") or []
    ids = [case.get("id") for case in cases]
    results = []
    for case in cases:
        category = classify_question(case.get("question", ""), "information")
        actual_method = (
            "refusal"
            if category in {"unsupported", "sensitive_or_individual_request"}
            else route_question(case.get("question", ""))
        )
        checks = {
            "schema": _REQUIRED_CASE_FIELDS <= case.keys()
            and bool(case.get("expected_methods")),
            "category": category == case.get("expected_category"),
            "method": actual_method
            in case.get("offline_expected_methods", case.get("expected_methods", [])),
            "refusal": not (
                case.get("refusal_required")
                and case.get("expected_category")
                in {"unsupported", "sensitive_or_individual_request"}
            )
            or actual_method == "refusal",
        }
        results.append(
            {
                "id": case.get("id", "missing-id"),
                "family": case.get("family", "missing-family"),
                "checks": checks,
                "passed": all(checks.values()),
                "available": True,
                "actual_category": category,
                "actual_method": actual_method,
                "duration_ms": 0,
            }
        )

    total = len(results)
    refusals = [
        result
        for case, result in zip(cases, results)
        if case.get("refusal_required")
        and case.get("expected_category")
        in {"unsupported", "sensitive_or_individual_request"}
    ]

    def rate(check: str, population: list[dict[str, Any]] = results) -> float:
        if not population:
            return 0.0
        return sum(item["checks"][check] for item in population) / len(population)

    metrics = {
        "schema_compliance": rate("schema")
        if len(ids) == len(set(ids)) and all(ids)
        else 0.0,
        "category_accuracy": rate("category"),
        "method_accuracy": rate("method"),
        "refusal_recall": rate("refusal", refusals),
        "passed_cases": sum(result["passed"] for result in results),
        "total_cases": total,
    }
    metrics["case_pass_rate"] = metrics["passed_cases"] / total if total else 0.0
    thresholds = dataset["offline_thresholds"]
    threshold_checks = {
        name: metrics[name] >= threshold for name, threshold in thresholds.items()
    }
    return {
        "evaluation_mode": "offline",
        "dataset_version": dataset["dataset_version"],
        "status": "PASS" if all(threshold_checks.values()) else "FAIL",
        "metrics": metrics,
        "thresholds": thresholds,
        "threshold_checks": threshold_checks,
        "results": results,
    }


def http_transport(base_url: str, token: str = "") -> Transport:
    parsed_url = urlparse(base_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.hostname:
        raise ValueError("base_url must use http or https and include a host")
    endpoint = f"{base_url.rstrip('/')}/v1/answers"

    def send(question: str) -> dict[str, Any]:
        body = json.dumps({"question": question, "mode": "information"}).encode()
        headers = {"Content-Type": "application/json"}
        if token:
            headers["X-Internal-Token"] = token
        try:
            # The configurable URL is restricted to HTTP(S) with a valid host above.
            with request.urlopen(  # nosec B310
                request.Request(endpoint, data=body, headers=headers), timeout=120
            ) as response:
                return json.loads(response.read())
        except error.HTTPError as exc:
            raise RuntimeError(f"assistant_http_{exc.code}") from exc

    return send


def write_reports(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "rag_evaluation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    metrics = report["metrics"]
    lines = [
        "# Évaluation RAG",
        "",
        f"Statut : **{report['status']}**",
        "",
        f"- Dataset : `{report['dataset_version']}`",
        f"- Cas réussis : {metrics['passed_cases']}/{metrics['total_cases']}",
        f"- Mode : `{report.get('evaluation_mode', 'live')}`",
        *(
            [f"- Disponibilité : {metrics['availability']:.1%}"]
            if "availability" in metrics
            else []
        ),
        f"- Exactitude catégorie : {metrics['category_accuracy']:.1%}",
        f"- Exactitude méthode : {metrics['method_accuracy']:.1%}",
        f"- Rappel des refus : {metrics['refusal_recall']:.1%}",
        *(
            [f"- Conformité des preuves : {metrics['evidence_compliance']:.1%}"]
            if "evidence_compliance" in metrics
            else []
        ),
        "",
        "## Cas en échec",
        "",
    ]
    failed = [result for result in report["results"] if not result["passed"]]
    lines.extend(
        f"- `{result['id']}` : {result.get('error') or result.get('checks')}"
        for result in failed
    )
    if not failed:
        lines.append("Aucun.")
    (output_dir / "rag_evaluation.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evaluate-rag")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("assistant_api/evaluation_dataset.json"),
    )
    parser.add_argument("--base-url", default=os.getenv("ASSISTANT_API_BASE_URL", "http://localhost:8030"))
    parser.add_argument("--output-dir", type=Path, default=Path("app/reports/rag"))
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args(argv)
    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    report = (
        evaluate_offline_dataset(dataset)
        if args.offline
        else evaluate_dataset(
            dataset,
            http_transport(args.base_url, os.getenv("ASSISTANT_INTERNAL_TOKEN", "")),
        )
    )
    write_reports(report, args.output_dir)
    print(json.dumps({"status": report["status"], **report["metrics"]}))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
