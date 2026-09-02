from unittest.mock import Mock, patch

from app.core import analytics
from src.storage.database import get_database_url


def test_operational_render_postgres_url_selects_psycopg(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://user:password@render-db:5432/staging"
    )

    assert get_database_url() == (
        "postgresql+psycopg://user:password@render-db:5432/staging"
    )


@patch("app.core.analytics.create_engine")
def test_analytics_render_postgres_url_selects_psycopg(create_engine, monkeypatch):
    monkeypatch.setattr(
        analytics.settings,
        "ANALYTICS_DATABASE_URL",
        "postgresql://user:password@render-db:5432/staging",
    )
    connection = Mock()
    create_engine.return_value.begin.return_value.__enter__.return_value = connection

    with analytics.analytics_connection() as opened:
        assert opened is connection

    create_engine.assert_called_once_with(
        "postgresql+psycopg://user:password@render-db:5432/staging",
        future=True,
    )
