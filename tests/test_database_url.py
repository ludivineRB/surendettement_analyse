from src.storage.database import normalize_postgres_url


def test_render_database_url_uses_psycopg():
    assert normalize_postgres_url(
        "postgresql://user:password@host/database"
    ) == "postgresql+psycopg://user:password@host/database"


def test_explicit_psycopg_database_url_is_preserved():
    database_url = "postgresql+psycopg://user:password@host/database"

    assert normalize_postgres_url(database_url) == database_url
