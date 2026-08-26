import json
from copy import deepcopy
from pathlib import Path

from benchmark.evaluation import evaluate_dataset, write_reports


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
