"""Explicit, idempotent provisioning of the PostgreSQL analytics role."""

from __future__ import annotations

import os

from psycopg import sql
from sqlalchemy import Engine, create_engine, text

ROLE_NAME = "analytics_readonly"
ALLOWED_VIEWS = frozenset(
    {
        "analytics_risk_scores",
        "analytics_score_factors",
        "analytics_observations",
        "analytics_model_comparisons",
        "analytics_pipeline_status",
    }
)


class ReadonlyRoleConfigurationError(RuntimeError):
    pass


def configure_role(engine: Engine, password: str) -> None:
    if not password:
        raise ReadonlyRoleConfigurationError("Mot de passe analytique requis.")
    with engine.begin() as connection:
        exists = connection.execute(
            text("SELECT 1 FROM pg_roles WHERE rolname = :role"),
            {"role": ROLE_NAME},
        ).scalar_one_or_none()
        if not exists:
            connection.exec_driver_sql(
                "CREATE ROLE analytics_readonly LOGIN NOSUPERUSER "
                "NOCREATEDB NOCREATEROLE NOINHERIT"
            )
        raw_connection = connection.connection.driver_connection
        with raw_connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("ALTER ROLE {} PASSWORD {}").format(
                    sql.Identifier(ROLE_NAME),
                    sql.Literal(password),
                )
            )
        connection.exec_driver_sql(
            "ALTER ROLE analytics_readonly SET default_transaction_read_only = on"
        )
        connection.exec_driver_sql(
            "ALTER ROLE analytics_readonly SET statement_timeout = '5s'"
        )
        grant_connect = connection.execute(
            text(
                "SELECT format('GRANT CONNECT ON DATABASE %I "
                "TO analytics_readonly', current_database())"
            )
        ).scalar_one()
        connection.exec_driver_sql(grant_connect)
        connection.exec_driver_sql(
            "REVOKE ALL ON ALL TABLES IN SCHEMA public FROM analytics_readonly"
        )
        connection.exec_driver_sql(
            "REVOKE ALL ON SCHEMA public FROM analytics_readonly"
        )
        connection.exec_driver_sql("GRANT USAGE ON SCHEMA public TO analytics_readonly")
        for view in sorted(ALLOWED_VIEWS):
            connection.exec_driver_sql(f"GRANT SELECT ON {view} TO analytics_readonly")


def main() -> int:
    if os.getenv("CONFIRM_ANALYTICS_ROLE") != "yes":
        raise ReadonlyRoleConfigurationError(
            "Définissez CONFIRM_ANALYTICS_ROLE=yes pour configurer le rôle."
        )
    admin_url = os.getenv("ADMIN_DATABASE_URL", "").strip()
    password = os.getenv("ANALYTICS_READONLY_PASSWORD", "")
    if not admin_url.startswith("postgresql+psycopg://"):
        raise ReadonlyRoleConfigurationError(
            "ADMIN_DATABASE_URL doit utiliser postgresql+psycopg."
        )
    configure_role(create_engine(admin_url, future=True), password)
    print("Rôle analytics_readonly configuré sur les vues autorisées.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
