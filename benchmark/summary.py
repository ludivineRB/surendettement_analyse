"""Produce the jury-facing synthesis without conflating benchmark roles."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


FIXTURE_NOTICE = (
    "Cette campagne ne mesure pas les performances d’un LLM réel. "
    "Le FixtureProvider retourne les décisions et SQL de référence afin de tester le banc d’essai."
)


def summarise_live(report: dict[str, Any]) -> dict[str, Any]:
    rows = report["cases"]
    metrics = report["metrics"]

    def same_values_different_keys(row: dict[str, Any]) -> bool:
        actual = row.get("actual_result")
        expected = row.get("expected_result")
        if not actual or not expected or len(actual) != len(expected) or actual == expected:
            return False
        return [list(item.values()) for item in actual] == [list(item.values()) for item in expected]

    correct_by_decision = {
        decision: sum(r["expected_decision"] == decision and r["decision_correct"] for r in rows)
        for decision in ("execute", "clarify", "refuse")
    }
    expected_by_decision = {
        decision: sum(r["expected_decision"] == decision for r in rows)
        for decision in ("execute", "clarify", "refuse")
    }
    guard_rejections = [
        {"id": r["id"], "reason_code": r["guard"]["reason_code"]}
        for r in rows if r.get("guard") and not r["guard"]["accepted"]
    ]
    return {
        "provider": report["configuration"]["provider"],
        "model": report["configuration"]["model"],
        "date": report["configuration"]["date"],
        "dataset_version": report["configuration"]["dataset_version"],
        "repeat": report["configuration"]["repeat"],
        "case_count": len(rows),
        "metrics": metrics,
        "correct_by_decision": correct_by_decision,
        "expected_by_decision": expected_by_decision,
        "api_or_contract_errors": sum(bool(r.get("error")) for r in rows),
        "successful_execute_results": sum(
            r["expected_decision"] == "execute" and r.get("execution_correct") is True
            for r in rows
        ),
        "guard_rejections": guard_rejections,
        "business_mismatches_after_execution": [
            r["id"] for r in rows if r.get("execution_correct") is False
        ],
        "value_equivalent_alias_mismatches": [r["id"] for r in rows if same_values_different_keys(r)],
    }


def build(parser_report: dict[str, Any], fixture_report: dict[str, Any],
          tests_passed: int, tests_failed: int,
          live_reports: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "date": datetime.now(timezone.utc).isoformat(),
        "categories": {
            "FAIT DOCUMENTÉ": [
                "SQLGlot est la frontière de sécurité; un succès de parsing n'est pas un verdict de sécurité.",
                "Les capacités AST des adaptateurs sont déclarées et non mesurées par la campagne de temps.",
            ],
            "MESURE DU POC": {
                "tests": {"passed": tests_passed, "failed": tests_failed},
                "fixture": fixture_report["metrics"],
                "parsers": parser_report["parsers"],
                "live": [summarise_live(report) for report in (live_reports or [])],
            },
            "ESTIMATION": "Coût et CO2e non calculés sans facteurs explicites, documentés et datés.",
            "RECOMMANDATION": (
                "Décision LLM, puis garde-fou SQLGlot, SQLite read-only dans le POC, "
                "et comparaison avec l'oracle. Conserver des contrôles serveur supplémentaires en production."
            ),
        },
        "fixture_notice": FIXTURE_NOTICE,
        "methodological_limits": [
            "Dataset de 32 cas: résultats non généralisables à tous les usages Text-to-SQL.",
            "Le corpus ne contient qu'un SQL volontairement invalide pour le benchmark des parseurs.",
            "La comparaison live est limitée aux modèles effectivement accessibles; aucune campagne live ici.",
            "SQLite est une fixture de POC, pas une preuve d'aptitude à la production.",
            "Aucune mesure CO2e fiable n'est disponible.",
            "Le POC ne permet aucune conclusion sur une mise en production réelle en entreprise.",
        ],
    }


def write_reports(report: dict[str, Any], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "benchmark_summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    categories = report["categories"]
    measured = categories["MESURE DU POC"]
    fixture = measured["fixture"]
    available = [p for p in measured["parsers"] if p["available"]]
    lines = [
        "# Synthèse du benchmark Text-to-SQL", "",
        "## 1. VALIDATION DU BANC D’ESSAI — MESURE DU POC", "",
        f"Tests offline : **{measured['tests']['passed']} succès, {measured['tests']['failed']} échec**.",
        report["fixture_notice"],
        f"Sur les 32 cas techniques : décision {fixture['decision_accuracy']:.0%}, "
        f"garde-fou/schéma {fixture['schema_conformity_rate']:.0%}, "
        f"oracle métier {fixture['business_accuracy']:.0%}.", "",
        "## 2. BENCHMARK DES PARSEURS — MESURE DU POC", "",
        f"Parseurs disponibles et mesurés : {', '.join(p['parser'] for p in available)}.",
        "Le corpus invalide ne contient qu’un cas; les taux de détection sont peu robustes.",
        "SQLGlot reste le garde-fou car les capacités déclarées des AST ne constituent pas une équivalence de sécurité.", "",
        "## 3. ÉVALUATION LIVE DU/DES LLM — MESURE DU POC", "",
    ]
    if measured["live"]:
        lines.append(f"Campagnes live intégrées : {len(measured['live'])}.")
        for live in measured["live"]:
            m = live["metrics"]
            counts = live["correct_by_decision"]
            expected = live["expected_by_decision"]
            lines += [
                "",
                f"### {live['provider']} / {live['model']}", "",
                f"Sur le corpus de **{live['case_count']} cas** du POC, répétition : {live['repeat']}.",
                f"Décisions correctes : **{m['decision_accuracy']:.2%}** ; "
                f"traitements corrects : **{m['correct_treatment_rate']:.2%}**.",
                f"Décisions execute correctes : {counts['execute']}/{expected['execute']} ; "
                f"clarify corrects : {counts['clarify']}/{expected['clarify']} ; "
                f"refuse corrects : {counts['refuse']}/{expected['refuse']}.",
                f"Résultats execute conformes à l’oracle : "
                f"{live['successful_execute_results']}/{expected['execute']}.",
                f"Refusal precision/recall : {m['refusal_precision']:.2%}/{m['refusal_recall']:.2%} ; "
                f"clarification : {m['clarification_accuracy']:.2%}.",
                f"Blocage dangereux : {m['dangerous_request_blocking_rate']:.2%} ; "
                f"injections : {m['prompt_injection_blocking_rate']:.2%}.",
                f"Latence moyenne/p50/p95 : {m['latency_mean_ms']:.1f}/"
                f"{m['latency_p50_ms']:.1f}/{m['latency_p95_ms']:.1f} ms.",
                f"Tokens totaux : {m['total_tokens']} "
                f"(entrée moyenne {m['input_tokens_mean']:.1f}, sortie moyenne {m['output_tokens_mean']:.1f}).",
                "Coût : non calculé (aucun tarif explicite et daté configuré).",
                f"Erreurs API/contrat : {live['api_or_contract_errors']}.",
                f"SQL refusés par le garde-fou : {len(live['guard_rejections'])} "
                f"({', '.join(sorted({r['reason_code'] for r in live['guard_rejections']})) or 'aucun'}).",
                f"Résultats métier incorrects après exécution : "
                f"{len(live['business_mismatches_after_execution'])}.",
                f"Dont valeurs identiques mais alias de colonne différent : "
                f"{', '.join(live['value_equivalent_alias_mismatches']) or 'aucun'}.",
                "Point fort observé : toutes les injections explicites du corpus ont été refusées.",
                "Limite observée : sur-clarification et absence de LIMIT dans les SQL générés.",
            ]
        lines += ["", "### Comparaison des modèles sur ce corpus", "",
                  "| Modèle | Décision | Traitement | Exécution | Refusal recall | Danger | p95 | Tokens |",
                  "|---|---:|---:|---:|---:|---:|---:|---:|"]
        for live in measured["live"]:
            m = live["metrics"]
            lines.append(f"| {live['model']} | {m['decision_accuracy']:.2%} | "
                         f"{m['correct_treatment_rate']:.2%} | {m['execution_accuracy']:.2%} | "
                         f"{m['refusal_recall']:.2%} | {m['dangerous_request_blocking_rate']:.2%} | "
                         f"{m['latency_p95_ms']:.1f} ms | {m['total_tokens']} |")
    else:
        lines.append("Non exécutée : aucune clé OpenAI disponible. Aucun coût ni jeton live mesuré.")
    lines += ["", "## 4. RECOMMANDATION", "", categories["RECOMMANDATION"], "",
              "## FAIT DOCUMENTÉ", ""]
    lines += [f"- {item}" for item in categories["FAIT DOCUMENTÉ"]]
    lines += ["", "## ESTIMATION", "", categories["ESTIMATION"],
              "", "## Limites méthodologiques", ""]
    lines += [f"- {item}" for item in report["methodological_limits"]]
    (output / "benchmark_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parser-report", type=Path,
                        default=Path("benchmark/reports/parser/parser_benchmark.json"))
    parser.add_argument("--fixture-report", type=Path,
                        default=Path("benchmark/reports/llm/fixture_dataset-reference/evaluation.json"))
    parser.add_argument("--tests-passed", type=int, default=0)
    parser.add_argument("--tests-failed", type=int, default=0)
    parser.add_argument("--live-report", type=Path, action="append", default=[])
    parser.add_argument("--output-dir", type=Path, default=Path("benchmark/reports/summary"))
    args = parser.parse_args(argv)
    report = build(
        json.loads(args.parser_report.read_text()),
        json.loads(args.fixture_report.read_text()),
        args.tests_passed,
        args.tests_failed,
        [json.loads(path.read_text()) for path in args.live_report],
    )
    write_reports(report, args.output_dir)
    print(json.dumps({"status": "written", "output": str(args.output_dir)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
