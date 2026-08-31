"""Combine parser and LLM reports without conflating their responsibilities."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


def build(parser_report: dict[str, Any], llm_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "date": datetime.now(timezone.utc).isoformat(),
        "documented_fact": "Parser benchmarks measure parsing; SQLGlot validation is the security boundary.",
        "poc_measurement": {"parsers": parser_report["parsers"], "llm": llm_report["metrics"]},
        "estimate": "No CO2e estimate and no cost estimate without documented dated factors.",
        "recommendation": "LLM decision -> SQLGlot guard -> read-only SQLite -> oracle comparison.",
    }


def write_reports(report: dict[str, Any], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "benchmark_summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    lines = ["# Synthèse du benchmark", "", "## FAIT DOCUMENTÉ", "", report["documented_fact"],
             "", "## MESURE DU POC", "", f"Métriques LLM : `{json.dumps(report['poc_measurement']['llm'])}`",
             f"Parseurs mesurés : {len(report['poc_measurement']['parsers'])}.", "", "## ESTIMATION", "",
             report["estimate"], "", "## RECOMMANDATION", "", report["recommendation"]]
    (output / "benchmark_summary.md").write_text("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parser-report", type=Path,
                        default=Path("benchmark/reports/parser/parser_benchmark.json"))
    parser.add_argument("--llm-report", type=Path,
                        default=Path("benchmark/reports/llm/fixture_dataset-reference/evaluation.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("benchmark/reports/summary"))
    args = parser.parse_args(argv)
    report = build(json.loads(args.parser_report.read_text()), json.loads(args.llm_report.read_text()))
    write_reports(report, args.output_dir)
    print(json.dumps({"status": "written", "output": str(args.output_dir)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
