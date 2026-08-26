import pytest

from assistant_api.sql_validation import SQLValidationError, validate_analytical_sql


def test_accepts_bounded_select_on_allowlisted_view():
    result = validate_analytical_sql(
        "SELECT geographic_code, score FROM analytics_risk_scores "
        "WHERE reference_period = '2025' ORDER BY score DESC LIMIT 10"
    )
    assert result.tables == ("analytics_risk_scores",)
    assert result.limit == 10


def test_accepts_allowlisted_aggregate_with_boolean_filters():
    result = validate_analytical_sql(
        "SELECT geographic_name, AVG(score) AS average_score "
        "FROM analytics_risk_scores "
        "WHERE geographic_level = 'region' AND reference_period = '2025-02' "
        "GROUP BY geographic_name LIMIT 200"
    )
    assert result.limit == 200


@pytest.mark.parametrize(
    ("sql", "code"),
    [
        ("DROP TABLE analytics_risk_scores", "read_only_required"),
        ("UPDATE analytics_risk_scores SET score = 0 LIMIT 1", "read_only_required"),
        ("SELECT score FROM analytics_risk_scores LIMIT 1; SELECT 1", "multiple_statements"),
        ("SELECT score FROM analytics_risk_scores -- LIMIT 1", "comments_forbidden"),
        ("SELECT pg_sleep(10) FROM analytics_risk_scores LIMIT 1", "function_forbidden"),
        ("SELECT password FROM auth_user LIMIT 1", "table_forbidden"),
        ("SELECT score FROM analytics_risk_scores", "limit_required"),
        ("SELECT score FROM analytics_risk_scores LIMIT 10000", "invalid_limit"),
        ("SELECT * FROM analytics_risk_scores LIMIT 10", "wildcard_forbidden"),
        ("COPY analytics_risk_scores TO '/tmp/data'", "read_only_required"),
        ("SELECT secret_value FROM analytics_risk_scores LIMIT 1", "column_forbidden"),
        ("SELECT x.score FROM analytics_risk_scores r LIMIT 1", "column_forbidden"),
    ],
)
def test_rejects_unsafe_sql(sql, code):
    with pytest.raises(SQLValidationError) as error:
        validate_analytical_sql(sql)
    assert error.value.code == code


def test_rejects_more_than_three_joins():
    sql = "SELECT a.score FROM analytics_risk_scores a " + " ".join(
        f"JOIN analytics_risk_scores j{i} ON j{i}.id = a.id" for i in range(4)
    ) + " LIMIT 10"
    with pytest.raises(SQLValidationError) as error:
        validate_analytical_sql(sql)
    assert error.value.code == "too_many_joins"


def test_rejects_unqualified_column_shared_by_joined_views():
    sql = (
        "SELECT geographic_code FROM analytics_risk_scores scores "
        "JOIN analytics_score_factors factors "
        "ON factors.geographic_code = scores.geographic_code LIMIT 10"
    )
    with pytest.raises(SQLValidationError) as error:
        validate_analytical_sql(sql)
    assert error.value.code == "column_ambiguous"


def test_accepts_qualified_columns_and_projection_alias():
    result = validate_analytical_sql(
        "SELECT scores.geographic_code, AVG(scores.score) AS average_score "
        "FROM analytics_risk_scores scores "
        "JOIN analytics_score_factors factors "
        "ON factors.geographic_code = scores.geographic_code "
        "GROUP BY scores.geographic_code ORDER BY average_score DESC LIMIT 10"
    )
    assert result.tables == ("analytics_risk_scores", "analytics_score_factors")
