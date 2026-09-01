"""Reusable internal-token authentication for protected FastAPI routes."""

from __future__ import annotations

import os
import secrets

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader


internal_token_header = APIKeyHeader(
    name="X-Internal-Token",
    scheme_name="InternalToken",
    description=(
        "Jeton interne fourni par la variable d'environnement "
        "ASSISTANT_INTERNAL_TOKEN."
    ),
    auto_error=False,
)


def get_internal_token(
    supplied_token: str | None = Security(internal_token_header),
) -> str | None:
    """Expose the optional credential for conditionally protected operations."""
    return supplied_token


def require_internal_token(
    supplied_token: str | None = Security(internal_token_header),
) -> None:
    """Require the configured internal token without exposing its value."""
    configured_token = os.getenv("ASSISTANT_INTERNAL_TOKEN", "").strip()
    if not supplied_token:
        raise HTTPException(status_code=401, detail="Authentification requise.")
    if not configured_token or not secrets.compare_digest(
        configured_token,
        supplied_token,
    ):
        raise HTTPException(status_code=403, detail="Accès non autorisé.")
