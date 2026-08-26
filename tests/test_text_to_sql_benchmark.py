import json
import os
from copy import deepcopy
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from assistant_api.sql_executor import execute_readonly_sql
from benchmark.evaluation import evaluate_dataset, evaluate_reference_results, write_reports


DATASET_PATH = Path("benchmark/text_to_sql_dataset.json")


def _dataset():
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


def test_offline_dataset_contract_and_adversarial_sql_pass():
    report = evaluate_dataset(_dataset())

    assert report["status"] == "PASS"
    assert report["contract_errors"] == []
    assert report["metrics"]["evaluated_sql_cases"] == 10
    assert report["metrics"]["adversarial_block_rate"] == 1.0
    assert report["metrics"]["refusal_reason_accuracy"] == 1.0
    assert report["metrics"]["reference_sql_cases"] == 9
    assert report["metrics"]["reference_sql_compliance"] == 1.0


def test_safe_sql_masquerading_as_adversarial_fails_the_threshold():
    dataset = deepcopy(_dataset())
    target = next(case for case in dataset["cases"] if case.get("adversarial_sql"))
    target["adversarial_sql"] = "SELECT score FROM analytics_risk_scores LIMIT 1"

    report = evaluate_dataset(dataset)

    assert report["status"] == "FAIL"
    assert report["metrics"]["adversarial_block_rate"] < 1.0


def test_duplicate_case_ids_fail_contract_validation():
    dataset = deepcopy(_dataset())
    dataset["cases"][1]["id"] = dataset["cases"][0]["id"]

    report = evaluate_dataset(dataset)

    assert report["status"] == "FAIL"
    assert "case_ids_must_be_unique" in report["contract_errors"]


def test_reports_are_written_as_json_and_markdown(tmp_path):
    report = evaluate_dataset(_dataset())

    write_reports(report, tmp_path)

    assert json.loads((tmp_path / "evaluation.json").read_text())["status"] == "PASS"
    assert "Statut : **PASS**" in (tmp_path / "evaluation.md").read_text()


@pytest.mark.postgres_integration
def test_reference_queries_match_business_oracles_on_disposable_postgres_fixture():
    database_url = os.getenv("TEST_POSTGRES_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_POSTGRES_DATABASE_URL is not configured")
    engine = create_engine(database_url, future=True, pool_size=1, max_overflow=0)
    statements = [
        "CREATE TEMP TABLE analytics_risk_scores (geographic_level text, "
        "geographic_code text, reference_period text, score numeric)",
        "INSERT INTO analytics_risk_scores VALUES "
        "('region','32','2025-02',60),('region','11','2025-02',30),"
        "('department','59','2025-02',70),('department','75','2025-02',50),"
        "('region','11','2025',20),('region','32','2025',40),"
        "('department','59','2024-02',55)",
        "CREATE TEMP TABLE analytics_macro_regions (reference_year integer, "
        "region_name text, indicator_code text, value_numeric numeric)",
        "INSERT INTO analytics_macro_regions VALUES "
        "(2022,'Hauts-de-France','taux_chomage_1564',9),"
        "(2022,'Île-de-France','taux_chomage_1564',7),"
        "(2022,'Hauts-de-France','part_familles_monoparentales',14),"
        "(2022,'Île-de-France','part_familles_monoparentales',10)",
        "CREATE TEMP TABLE analytics_score_factors (geographic_level text, "
        "geographic_code text, reference_period text, indicator_code text, "
        "contribution numeric)",
        "INSERT INTO analytics_score_factors VALUES "
        "('region','32','2025-02','taux_pauvrete',18),"
        "('region','32','2025-02','taux_chomage',12)",
        "CREATE TEMP TABLE analytics_model_comparisons (geographic_level text, "
        "geographic_code text, reference_period text, version_a text, version_b text, "
        "score_a numeric, score_b numeric, score_change numeric)",
        "INSERT INTO analytics_model_comparisons VALUES "
        "('department','59','2025-02','1.1.0','1.2.0',65,70,5),"
        "('department','75','2025-02','1.1.0','1.2.0',52,50,-2)",
    ]
    try:
        with engine.connect() as connection:
            for statement in statements:
                connection.exec_driver_sql(statement)
            connection.commit()
        results = evaluate_reference_results(
            _dataset(),
            lambda sql: execute_readonly_sql(sql, engine=engine).rows,
        )
        assert len(results) == 9
        assert all(result["passed"] for result in results), results
    finally:
        engine.dispose()
