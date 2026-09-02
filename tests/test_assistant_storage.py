import pytest

from assistant_api.migrations import migration_versions
from assistant_api.storage import (
    AssistantDatabaseConfigurationError,
    get_database_url,
)


def test_database_configuration_is_explicit(monkeypatch):
    monkeypatch.delenv("ASSISTANT_DATABASE_URL", raising=False)

    with pytest.raises(AssistantDatabaseConfigurationError):
        get_database_url()


def test_database_configuration_requires_psycopg(monkeypatch):
    monkeypatch.setenv("ASSISTANT_DATABASE_URL", "sqlite:///assistant.db")

    with pytest.raises(AssistantDatabaseConfigurationError):
        get_database_url()


def test_render_postgres_url_selects_psycopg_driver(monkeypatch):
    monkeypatch.setenv(
        "ASSISTANT_DATABASE_URL",
        "postgresql://user:password@render-db:5432/staging",
    )

    assert get_database_url() == (
        "postgresql+psycopg://user:password@render-db:5432/staging"
    )


def test_corpus_schema_has_a_versioned_first_migration():
    assert migration_versions() == (
        "001_corpus_chunks",
        "002_sql_execution_audit",
    )
