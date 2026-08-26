import json

from benchmark.poc import DEFAULT_CASE_IDS, ReferenceGenerator, run_poc


def test_reference_mode_exercises_all_strategies_without_database():
    dataset = json.loads(
        open("benchmark/text_to_sql_dataset.json", encoding="utf-8").read()
    )
    references = {
        case["question"]: case["reference_sql"]
        for case in dataset["cases"]
        if case.get("reference_sql")
    }

    report = run_poc(
        dataset,
        ReferenceGenerator(references),
        strategy_names=["current", "schema_only", "few_shot", "retrieval", "review"],
    )

    assert report["database_execution"] is False
    assert report["mode"] == "reference"
    assert len(report["results"]) == len(DEFAULT_CASE_IDS) * 5
    assert {row["strategy"] for row in report["summary"]} == {
        "current",
        "schema_only",
        "few_shot",
        "retrieval",
        "review",
    }
    review = next(row for row in report["summary"] if row["strategy"] == "review")
    assert review["calls"] > len(DEFAULT_CASE_IDS)
