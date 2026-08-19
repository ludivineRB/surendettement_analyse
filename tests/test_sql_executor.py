from unittest.mock import MagicMock

import pytest

from assistant_api.sql_executor import SQLCostError, execute_readonly_sql
from assistant_api.sql_validation import SQLValidationError


SAFE_SQL = (
    "SELECT geographic_code, score FROM analytics_risk_scores LIMIT 10"
)


def _engine(plan=None, rows=None):
    connection = MagicMock()
    transaction = MagicMock()
    connection.begin.return_value = transaction
    plan_result = MagicMock()
    plan_result.scalar_one.return_value = plan or [
        {"Plan": {"Total Cost": 12.5, "Plan Rows": 10}}
    ]
    query_result = MagicMock()
    query_result.mappings.return_value.all.return_value = rows or [
        {"geographic_code": "59", "score": 42}
    ]
    connection.execute.side_effect = [plan_result, query_result]
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = connection
    return engine, connection, transaction


def test_executes_explain_then_select_in_readonly_transaction():
    engine, connection, transaction = _engine()

    result = execute_readonly_sql(SAFE_SQL, engine=engine)

    assert result.rows[0]["score"] == 42
    assert result.plan_cost == 12.5
    assert connection.execute.call_count == 2
    connection.exec_driver_sql.assert_any_call("SET TRANSACTION READ ONLY")
    transaction.rollback.assert_called_once()


def test_rejects_unsafe_sql_before_connecting():
    engine, _, _ = _engine()
    with pytest.raises(SQLValidationError):
        execute_readonly_sql("DELETE FROM analytics_risk_scores", engine=engine)
    engine.connect.assert_not_called()


def test_rejects_excessive_plan_and_rolls_back():
    engine, connection, transaction = _engine(
        plan=[{"Plan": {"Total Cost": 100001, "Plan Rows": 10}}]
    )
    with pytest.raises(SQLCostError):
        execute_readonly_sql(SAFE_SQL, engine=engine)
    assert connection.execute.call_count == 1
    transaction.rollback.assert_called_once()
