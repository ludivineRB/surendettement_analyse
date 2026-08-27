"""Run the parser comparison corpus and write JSON and Markdown reports."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import median
from typing import Any

from cli import execute, generate_sql, parser_checks, schema_text, table_names, validate_read_only
from init_db import initialize


ROOT = Path(__file__).parent


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]


def normalize_row(row: tuple[object, ...]) -> tuple[object, ...]:
    return tuple(round(value, 8) if isinstance(value, float) else value for value in row)


def contains_values(actual: tuple[object, ...], required: tuple[object, ...]) -> bool:
    """Return whether required values occur in order, allowing extra columns."""
    iterator = iter(normalize_row(actual))
    return all(any(value == expected for value in iterator) for expected in normalize_row(required))


def results_match(
    actual: list[tuple[object, ...]], required: list[tuple[object, ...]], *, ordered: bool
) -> bool:
    if len(actual) != len(required):
        return False
    if ordered:
        return all(contains_values(row, expected) for row, expected in zip(actual, required))
    remaining = list(actual)
    for expected in required:
        match = next((index for index, row in enumerate(remaining) if contains_values(row, expected)), None)
        if match is None:
            return False
        remaining.pop(match)
    return True


def run(cases: list[dict[str, Any]], db: Path, *, live: bool, repeat: int) -> dict[str, Any]:
    schema = schema_text(db)
    allowed = table_names(db)
    rows: list[dict[str, Any]] = []
    for case in cases:
        reference_rows: list[tuple[object, ...]] = []
        if case["read_only"]:
            _, reference_rows = execute(db, case["sql"])
        sql = generate_sql(case["question"], schema) if live and case["read_only"] else case["sql"]
        print(f"[{case['id']}]\nSQL généré :\n{sql}\n")

        # Warm imports/caches before measuring repeated calls.
        parser_checks(sql)
        measurements: dict[str, dict[str, Any]] = {}
        for _ in range(repeat):
            for parser_name, status, elapsed_ms in parser_checks(sql):
                item = measurements.setdefault(parser_name, {"statuses": [], "times_ms": []})
                item["statuses"].append(status)
                item["times_ms"].append(elapsed_ms)

        guard_accepted = True
        guard_error = None
        result_rows: list[tuple[object, ...]] = []
        try:
            validate_read_only(sql, allowed)
            _, result_rows = execute(db, sql)
        except Exception as exc:
            guard_accepted = False
            guard_error = f"{type(exc).__name__}: {exc}"

        result_match = (
            results_match(result_rows, reference_rows, ordered=False)
            if case["read_only"] and guard_accepted
            else False if case["read_only"] else None
        )
        order_match = (
            results_match(result_rows, reference_rows, ordered=True)
            if case["read_only"] and guard_accepted
            else False if case["read_only"] else None
        )

        rows.append(
            {
                "id": case["id"],
                "question": case["question"],
                "sql": sql,
                "reference_sql": case["sql"] if case["read_only"] else None,
                "expected_read_only": case["read_only"],
                "guard_accepted": guard_accepted,
                "guard_correct": guard_accepted == case["read_only"],
                "guard_error": guard_error,
                "result_row_count": len(result_rows),
                "reference_row_count": len(reference_rows),
                "result_match": result_match,
                "order_match": order_match,
                "result_preview": [list(row) for row in result_rows[:5]],
                "parsers": {
                    name: {
                        "accepted": all(status == "OK" for status in data["statuses"]),
                        "status": data["statuses"][-1],
                        "median_ms": round(median(data["times_ms"]), 4),
                        "p95_ms": round(percentile(data["times_ms"], 0.95), 4),
                    }
                    for name, data in measurements.items()
                },
            }
        )

    parser_names = sorted({name for row in rows for name in row["parsers"]})
    summary = []
    for name in parser_names:
        available = [row["parsers"][name] for row in rows if not row["parsers"][name]["status"].startswith("INDISPONIBLE")]
        summary.append(
            {
                "parser": name,
                "available": bool(available),
                "accepted_cases": sum(item["accepted"] for item in available),
                "tested_cases": len(available),
                "median_ms": round(median([item["median_ms"] for item in available]), 4) if available else None,
                "p95_ms": round(percentile([item["p95_ms"] for item in available], 0.95), 4) if available else None,
            }
        )
    return {
        "mode": "live" if live else "reference",
        "repeat": repeat,
        "case_count": len(rows),
        "guard_correct": sum(row["guard_correct"] for row in rows),
        "execution_cases": sum(row["expected_read_only"] for row in rows),
        "execution_correct": sum(row["result_match"] is True for row in rows),
        "order_correct": sum(row["order_match"] is True for row in rows),
        "parser_summary": summary,
        "cases": rows,
    }


def markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Rapport du benchmark SQL",
        "",
        f"Mode : `{report['mode']}` — {report['case_count']} cas — {report['repeat']} répétitions.",
        f"Garde-fou correct : **{report['guard_correct']}/{report['case_count']}**.",
        f"Résultat métier correct : **{report['execution_correct']}/{report['execution_cases']}** "
        f"(ordre exact : {report['order_correct']}/{report['execution_cases']}).",
        "",
        "## Synthèse des parseurs",
        "",
        "| Parseur | Disponible | Cas acceptés | Médiane | p95 |",
        "|---|---:|---:|---:|---:|",
    ]
    for item in report["parser_summary"]:
        median_ms = f"{item['median_ms']:.4f} ms" if item["median_ms"] is not None else "—"
        p95_ms = f"{item['p95_ms']:.4f} ms" if item["p95_ms"] is not None else "—"
        lines.append(
            f"| {item['parser']} | {'oui' if item['available'] else 'non'} | "
            f"{item['accepted_cases']}/{item['tested_cases']} | {median_ms} | {p95_ms} |"
        )
    lines.extend([
        "",
        "## Détail des cas",
        "",
        "| Cas | Lecture attendue | Garde-fou | Résultat | Ordre | Lignes |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for case in report["cases"]:
        lines.append(
            f"| {case['id']} | {'oui' if case['expected_read_only'] else 'non'} | "
            f"{'correct' if case['guard_correct'] else 'incorrect'} | "
            f"{'correct' if case['result_match'] else 'incorrect' if case['result_match'] is False else '—'} | "
            f"{'correct' if case['order_match'] else 'incorrect' if case['order_match'] is False else '—'} | "
            f"{case['result_row_count']} |"
        )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Générer les SQL sûrs avec le LLM")
    parser.add_argument("--repeat", type=int, default=20)
    parser.add_argument("--cases", type=Path, default=ROOT / "cases.json")
    parser.add_argument("--db", type=Path, default=ROOT / "shop.db")
    parser.add_argument("--output", type=Path, default=ROOT / "report")
    args = parser.parse_args(argv)
    if args.repeat < 1:
        parser.error("--repeat doit être supérieur ou égal à 1")
    if not args.db.exists():
        initialize(args.db)
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    report = run(cases, args.db, live=args.live, repeat=args.repeat)
    args.output.with_suffix(".json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    args.output.with_suffix(".md").write_text(markdown(report), encoding="utf-8")
    print(f"Rapports : {args.output.with_suffix('.json')} et {args.output.with_suffix('.md')}")
    return 0 if report["guard_correct"] == report["case_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
