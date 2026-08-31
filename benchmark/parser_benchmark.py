"""Benchmark parser behaviour separately from the SQLGlot security guard."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib
import json
import math
from pathlib import Path
from statistics import mean, median
from time import perf_counter_ns
from typing import Any, Callable

from benchmark.dataset import load_dataset


CAPABILITIES = {
    "sqlglot": {"ast": True, "tables": True, "columns": True, "joins": True, "statement_type": True},
    "sqloxide": {"ast": True, "tables": True, "columns": True, "joins": True, "statement_type": True},
    "polyglot-sql": {"ast": True, "tables": True, "columns": True, "joins": True, "statement_type": True},
    "sqlparse": {"ast": False, "tables": False, "columns": False, "joins": False, "statement_type": "token_only"},
    "sqlfluff": {"ast": True, "tables": True, "columns": True, "joins": True, "statement_type": True},
    "datafusion": {"ast": False, "tables": True, "columns": True, "joins": True, "statement_type": "logical_plan"},
}
DEPENDENCIES = {"sqlglot": "light", "sqloxide": "rust binding", "polyglot-sql": "rust binding",
                "sqlparse": "light", "sqlfluff": "medium", "datafusion": "heavy/optional"}


def _adapters() -> dict[str, Callable[[str], object]]:
    return {
        "sqlglot": lambda sql: importlib.import_module("sqlglot").parse(sql, read="sqlite"),
        "sqloxide": lambda sql: importlib.import_module("sqloxide").parse_sql(sql, dialect="sqlite"),
        "polyglot-sql": lambda sql: importlib.import_module("polyglot_sql").parse(sql, dialect="sqlite"),
        "sqlparse": lambda sql: importlib.import_module("sqlparse").parse(sql),
        "sqlfluff": lambda sql: importlib.import_module("sqlfluff").parse(sql, dialect="sqlite"),
        "datafusion": lambda sql: importlib.import_module("datafusion").SessionContext().sql(sql),
    }


def percentile(values: list[float], fraction: float) -> float | None:
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)] if values else None


def run(repeat: int = 20) -> dict[str, Any]:
    dataset = load_dataset()
    corpus = [{"id": c["id"], "sql": c.get("oracle_sql") or c.get("adversarial_sql"),
               "valid": True} for c in dataset["cases"]]
    corpus = [case for case in corpus if case["sql"]]
    corpus.append({"id": "parser_invalid_sql", "sql": "SELECT FROM WHERE", "valid": False})
    results = []
    for name, parse in _adapters().items():
        times: list[float] = []
        exceptions: list[str] = []
        available = True
        outcomes = []
        for case in corpus:
            success = False
            ast_type = None
            for _ in range(repeat):
                started = perf_counter_ns()
                try:
                    ast = parse(case["sql"])
                    success = True
                    ast_type = type(ast).__name__
                except (ImportError, ModuleNotFoundError) as exc:
                    available = False
                    exceptions.append(type(exc).__name__)
                    break
                except Exception as exc:
                    exceptions.append(type(exc).__name__)
                finally:
                    times.append((perf_counter_ns() - started) / 1_000_000)
            outcomes.append({"id": case["id"], "expected_valid": case["valid"],
                             "parse_success": success, "ast_type": ast_type})
            if not available:
                break
        valid = [o for o in outcomes if o["expected_valid"]]
        invalid = [o for o in outcomes if not o["expected_valid"]]
        results.append({"parser": name, "available": available,
                        "parse_success_rate": sum(o["parse_success"] for o in valid) / len(valid) if valid else 0,
                        "invalid_sql_detection_rate": sum(not o["parse_success"] for o in invalid) / len(invalid) if invalid else 0,
                        "mean_ms": mean(times) if times else None, "p50_ms": median(times) if times else None,
                        "p95_ms": percentile(times, .95), "exceptions": sorted(set(exceptions)),
                        "capabilities": CAPABILITIES[name], "dependency": DEPENDENCIES[name],
                        "cases": outcomes})
    return {"configuration": {"date": datetime.now(timezone.utc).isoformat(), "repeat": repeat,
                               "dataset_version": dataset.get("dataset_version"), "dialect": "sqlite"},
            "notice": "Parsing capability is not a security verdict; SQLGlot remains the guard.",
            "parsers": results}


def write_reports(report: dict[str, Any], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "parser_benchmark.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    invalid_count = sum(not case["expected_valid"]
                        for parser in report["parsers"][:1] for case in parser["cases"])
    lines = ["# Benchmark des parseurs", "", report["notice"], "",
             f"Date : {report['configuration']['date']} — répétitions : {report['configuration']['repeat']}",
             f"Corpus invalide : {invalid_count} cas seulement; le taux de détection est donc peu robuste.",
             "", "## Résultats expérimentaux (MESURE DU POC)", "",
             "| Parseur | Disponible | Parse | SQL invalide détecté | Moyenne | p50 | p95 |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for p in report["parsers"]:
        timing = lambda key: f"{p[key]:.4f}" if p[key] is not None else "—"
        lines.append(f"| {p['parser']} | {'oui' if p['available'] else 'non'} | {p['parse_success_rate']:.0%} | "
                     f"{p['invalid_sql_detection_rate']:.0%} | {timing('mean_ms')} | {timing('p50_ms')} | "
                     f"{timing('p95_ms')} |")
    lines += ["", "## Capacités déclarées/implémentées (FAIT DOCUMENTÉ)", "",
              "Ces capacités proviennent des adaptateurs et ne sont pas mesurées par cette campagne.", "",
              "| Parseur | AST | Tables | Colonnes | JOIN | Statement | Dépendance |",
              "|---|---:|---:|---:|---:|---:|---|"]
    for p in report["parsers"]:
        c = p["capabilities"]
        lines.append(f"| {p['parser']} | {c['ast']} | {c['tables']} | {c['columns']} | "
                     f"{c['joins']} | {c['statement_type']} | {p['dependency']} |")
    lines += ["", "## Conclusion (RECOMMANDATION)", "",
              "Comparer richesse, erreurs, temps et dépendances; ne remplacer SQLGlot qu’après équivalence fonctionnelle démontrée."]
    (output / "parser_benchmark.md").write_text("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeat", type=int, default=20)
    parser.add_argument("--output-dir", type=Path, default=Path("benchmark/reports/parser"))
    args = parser.parse_args(argv)
    if args.repeat < 1:
        parser.error("--repeat must be >= 1")
    report = run(args.repeat)
    write_reports(report, args.output_dir)
    print(json.dumps([{k: p[k] for k in ("parser", "available", "parse_success_rate", "p95_ms")}
                      for p in report["parsers"]], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
