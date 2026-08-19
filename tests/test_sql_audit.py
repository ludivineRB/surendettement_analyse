from unittest.mock import MagicMock
from uuid import uuid4

from assistant_api.migrations import migration_versions
from assistant_api.repository import record_sql_execution


def test_sql_audit_migration_is_versioned():
    assert migration_versions()[-1] == "002_sql_execution_audit"


def test_sql_audit_is_bounded_and_ignores_unknown_fields():
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value
    payload = {
        "execution_id": uuid4(),
        "request_id": uuid4(),
        "actor_id": "user-42",
        "question": "q" * 3_000,
        "interpretation_json": "{}",
        "schema_version": "001",
        "generated_sql": "SELECT score FROM analytics_risk_scores LIMIT 1",
        "validation_status": "accepted",
        "validation_error": None,
        "duration_ms": 10,
        "row_count": 1,
        "plan_cost": 3.0,
        "prompt_version": "text-to-sql-v1",
        "model_version": "test-model",
        "database_password": "must-not-be-recorded",
    }

    record_sql_execution(engine, payload)

    parameters = connection.execute.call_args.args[1]
    assert len(parameters["question"]) == 2_000
    assert "database_password" not in parameters
