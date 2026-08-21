from assistant_api.evaluation import evaluate_case, evaluate_dataset


def _case(**overrides):
    case = {
        "id": "definition",
        "family": "simple",
        "question": "Définition ?",
        "expected_category": "documentary_question",
        "expected_methods": ["documents"],
        "evidence_required": True,
        "allowed_publishers": ["Insee"],
        "required_publishers": ["Insee"],
    }
    case.update(overrides)
    return case


def test_case_requires_expected_route_evidence_and_publishers():
    result = evaluate_case(
        _case(),
        {
            "category": "documentary_question",
            "method": "documents",
            "sources": [{"publisher": "Insee"}],
            "data_references": [],
            "generated_sql": None,
        },
    )
    assert result["passed"] is True


def test_case_accepts_other_allowed_official_publishers():
    result = evaluate_case(
        _case(allowed_publishers=["Insee", "Banque de France"]),
        {
            "category": "documentary_question",
            "method": "documents",
            "sources": [
                {"publisher": "Insee"},
                {"publisher": "Banque de France"},
            ],
            "data_references": [],
            "generated_sql": None,
        },
    )
    assert result["passed"] is True


def test_dataset_fails_when_a_required_refusal_is_not_enforced():
    case = _case(
        id="injection",
        family="injection",
        expected_category="unsupported",
        expected_methods=["refusal"],
        refusal_required=True,
        evidence_required=False,
        allowed_publishers=[],
    )
    dataset = {
        "dataset_version": "test",
        "thresholds": {"refusal_recall": 1.0},
        "cases": [case],
    }
    report = evaluate_dataset(
        dataset,
        lambda question: {
            "category": "documentary_question",
            "method": "documents",
            "sources": [],
            "data_references": [],
            "generated_sql": None,
        },
    )
    assert report["status"] == "FAIL"
    assert report["metrics"]["refusal_recall"] == 0.0
