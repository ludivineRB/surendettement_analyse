"""Idempotent end-to-end refresh with persistent execution journal and gates."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Callable

from sqlalchemy import func, select

from src.inclusion_financiere import InclusionFinancialPipeline
from src.observability import build_observability_report
from src.risk_score.department_debt_import import import_department_rates
from src.risk_score.historical_harmonization import (
    harmonize_historical_departments,
)
from src.risk_score.inflation_import import import_inflation
from src.risk_score.endettement_import import import_mean_debt
from src.risk_score.migrate import migrate_and_seed
from src.risk_score.service import RiskScoreCalculator
from src.storage.database import get_session_factory, init_db
from src.storage.models import InclusionObservation, PipelineRun

PIPELINE_NAME = "territorial-risk-refresh-v1"


def refresh_all(
    *,
    from_period: str,
    to_period: str | None = None,
    department_years: tuple[int, ...] = (2023, 2024, 2025),
    dry_run: bool = False,
    steps: list[tuple[str, Callable[[], object]]] | None = None,
) -> dict:
    init_db()
    configuration = {
        "from_period": from_period,
        "to_period": to_period,
        "department_years": list(department_years),
        "dry_run": dry_run,
    }
    run_id = _start_run(configuration)
    step_results = {}
    try:
        effective_steps = steps or _default_steps(
            from_period, to_period, department_years, dry_run
        )
        for name, operation in effective_steps:
            step_results[name] = _jsonable(operation())
            _update_run(run_id, step_results=step_results)
        quality = run_quality_gates()
        status = "success" if quality["passed"] else "quality_failed"
        _finish_run(run_id, status, step_results, quality)
        return {
            "run_id": run_id,
            "status": status,
            "steps": step_results,
            "quality": quality,
        }
    except Exception as exc:
        _finish_run(
            run_id,
            "failed",
            step_results,
            {},
            error_message=str(exc),
        )
        raise


def run_quality_gates() -> dict:
    observability = build_observability_report()
    factory = get_session_factory()
    with factory() as session:
        annual_coverage = {
            (str(period), indicator_code): int(count)
            for period, indicator_code, count in session.execute(
                select(
                    InclusionObservation.reference_period,
                    InclusionObservation.indicator_code,
                    func.count(func.distinct(InclusionObservation.geographic_code)),
                )
                .where(
                    InclusionObservation.geographic_level == "department",
                    InclusionObservation.indicator_code.in_(
                        (
                            "dossiers_surendettement_1000_habitants",
                            "endettement_moyen",
                        )
                    ),
                    InclusionObservation.reference_period.in_(("2023", "2024")),
                )
                .group_by(
                    InclusionObservation.reference_period,
                    InclusionObservation.indicator_code,
                )
            )
        }
    errors = [
        alert
        for alert in observability["alerts"]
        if alert["severity"] == "error"
    ]
    checks = {
        "no_integrity_errors": not errors,
        "department_2023_complete": annual_coverage.get(
            ("2023", "dossiers_surendettement_1000_habitants")
        )
        == 96,
        "department_2024_complete": annual_coverage.get(
            ("2024", "dossiers_surendettement_1000_habitants")
        )
        == 96,
        "mean_debt_2023_complete": annual_coverage.get(
            ("2023", "endettement_moyen")
        )
        == 96,
        "mean_debt_2024_complete": annual_coverage.get(
            ("2024", "endettement_moyen")
        )
        == 96,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "error_alerts": errors,
        "warning_alerts": [
            alert
            for alert in observability["alerts"]
            if alert["severity"] == "warning"
        ],
    }


def _default_steps(from_period, to_period, department_years, dry_run):
    inclusion_args = SimpleNamespace(
        command="run",
        from_period=from_period,
        to_period=to_period,
        regions=None,
        force=False,
        dry_run=dry_run,
        no_load=False,
    )
    calculator = RiskScoreCalculator()
    return [
        ("migrate", migrate_and_seed),
        (
            "monthly_bdf",
            lambda: InclusionFinancialPipeline().run(inclusion_args),
        ),
        *[
            (
                f"department_bdf_{year}",
                lambda year=year: import_department_rates(
                    year=year, dry_run=dry_run
                ),
            )
            for year in department_years
        ],
        (
            "historical_harmonization",
            lambda: harmonize_historical_departments(
                tuple(year for year in department_years if year in (2023, 2024)),
                dry_run=dry_run,
            ),
        ),
        (
            "mean_debt_bdf",
            lambda: import_mean_debt(
                department_years,
                dry_run=dry_run,
            ),
        ),
        ("inflation_insee", lambda: import_inflation(dry_run=dry_run)),
        (
            "regional_scores",
            lambda: calculator.calculate(
                "region", all_periods=True, dry_run=dry_run
            ).to_dict(),
        ),
        (
            "department_scores",
            lambda: calculator.calculate(
                "department", all_periods=True, dry_run=dry_run
            ).to_dict(),
        ),
    ]


def _start_run(configuration):
    factory = get_session_factory()
    with factory() as session:
        run = PipelineRun(
            pipeline_name=PIPELINE_NAME,
            status="running",
            configuration_json=json.dumps(configuration, ensure_ascii=False),
        )
        session.add(run)
        session.commit()
        return run.id


def _update_run(run_id, *, step_results):
    factory = get_session_factory()
    with factory() as session:
        run = session.get(PipelineRun, run_id)
        run.step_results_json = json.dumps(step_results, ensure_ascii=False)
        session.commit()


def _finish_run(
    run_id,
    status,
    step_results,
    quality,
    *,
    error_message=None,
):
    factory = get_session_factory()
    with factory() as session:
        run = session.get(PipelineRun, run_id)
        run.status = status
        run.finished_at = _now()
        run.step_results_json = json.dumps(step_results, ensure_ascii=False)
        run.quality_report_json = json.dumps(quality, ensure_ascii=False)
        run.error_message = error_message
        session.commit()


def _jsonable(value):
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return value


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def main(argv=None):
    parser = argparse.ArgumentParser(prog="pipeline-refresh")
    parser.add_argument("--from", dest="from_period", required=True)
    parser.add_argument("--to", dest="to_period")
    parser.add_argument(
        "--department-years",
        type=int,
        nargs="+",
        default=[2023, 2024, 2025],
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    result = refresh_all(
        from_period=args.from_period,
        to_period=args.to_period,
        department_years=tuple(args.department_years),
        dry_run=args.dry_run,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "success" else 2


if __name__ == "__main__":
    raise SystemExit(main())
