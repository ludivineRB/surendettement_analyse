"""Command line interface for risk score migration, calculation and inspection."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from src.risk_score.analytics_bridge import (
    DEFAULT_ANALYTICS_DB,
    import_analytics_indicators,
    report_as_dict,
)
from src.risk_score.filosofi_import import (
    import_filosofi,
    report_as_dict as filosofi_report_as_dict,
)
from src.risk_score.legacy_import import import_legacy_surendettement
from src.risk_score.migrate import migrate_and_seed
from src.risk_score.service import RiskScoreCalculator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="risk-score")
    commands = parser.add_subparsers(dest="command", required=True)

    migrate = commands.add_parser("migrate")
    migrate.add_argument("--mapping-json", type=Path)

    seed = commands.add_parser("seed")
    seed.add_argument("--mapping-json", type=Path)

    calculate = commands.add_parser("calculate")
    calculate.add_argument("--level", required=True)
    calculate.add_argument("--period")
    calculate.add_argument("--model", default="default")
    calculate.add_argument("--geographic-code")
    calculate.add_argument("--all-periods", action="store_true")
    calculate.add_argument("--dry-run", action="store_true")

    explain = commands.add_parser("explain")
    explain.add_argument("risk_score_id", type=int)

    legacy = commands.add_parser("import-legacy")
    legacy.add_argument("--dry-run", action="store_true")

    bridge = commands.add_parser("bridge-analytics")
    bridge.add_argument("--analytics-db", type=Path, default=DEFAULT_ANALYTICS_DB)
    bridge.add_argument("--dry-run", action="store_true")

    filosofi = commands.add_parser("import-filosofi")
    filosofi.add_argument("--source-zip", type=Path, required=True)
    filosofi.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command in {"migrate", "seed"}:
            print(json.dumps(migrate_and_seed(args.mapping_json), ensure_ascii=False, indent=2))
        elif args.command == "calculate":
            summary = RiskScoreCalculator().calculate(
                geographic_level=args.level,
                reference_period=args.period,
                model_code=args.model,
                geographic_code=args.geographic_code,
                all_periods=args.all_periods,
                dry_run=args.dry_run,
            )
            output = summary.to_dict()
            output["results"] = [asdict(result) for result in summary.results]
            print(json.dumps(output, ensure_ascii=False, indent=2))
        elif args.command == "explain":
            print(RiskScoreCalculator().explain(args.risk_score_id))
        elif args.command == "import-legacy":
            report = import_legacy_surendettement(dry_run=args.dry_run)
            print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
        elif args.command == "bridge-analytics":
            report = import_analytics_indicators(
                analytics_db=args.analytics_db,
                dry_run=args.dry_run,
            )
            print(json.dumps(report_as_dict(report), ensure_ascii=False, indent=2))
        else:
            report = import_filosofi(
                args.source_zip,
                dry_run=args.dry_run,
            )
            print(
                json.dumps(
                    filosofi_report_as_dict(report),
                    ensure_ascii=False,
                    indent=2,
                )
            )
        return 0
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
