from unittest.mock import MagicMock

import pytest
from psycopg import sql

from assistant_api.sql_validation import ALLOWED_VIEWS
from src.storage.configure_analytics_readonly import (
    ReadonlyRoleConfigurationError,
    configure_role,
)


def test_role_receives_only_select_on_allowlisted_views():
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value
    role_result = MagicMock()
    role_result.scalar_one_or_none.return_value = None
    database_result = MagicMock()
    database_result.scalar_one.return_value = (
        "GRANT CONNECT ON DATABASE test_db TO analytics_readonly"
    )
    connection.execute.side_effect = [role_result, database_result]

    configure_role(engine, "test-password")

    statements = [call.args[0] for call in connection.exec_driver_sql.call_args_list]
    grants = [statement for statement in statements if statement.startswith("GRANT SELECT")]
    assert grants == [f"GRANT SELECT ON {view} TO analytics_readonly" for view in sorted(ALLOWED_VIEWS)]
    assert all("INSERT" not in statement and "UPDATE" not in statement for statement in statements)
    assert "REVOKE ALL ON ALL TABLES IN SCHEMA public FROM analytics_readonly" in statements
    cursor = connection.connection.driver_connection.cursor.return_value.__enter__.return_value
    password_statement = cursor.execute.call_args.args[0]
    assert isinstance(password_statement, sql.Composed)
    assert all("test-password" not in statement for statement in statements)


def test_empty_password_is_rejected_before_database_access():
    engine = MagicMock()
    with pytest.raises(ReadonlyRoleConfigurationError):
        configure_role(engine, "")
    engine.begin.assert_not_called()
