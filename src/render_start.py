"""Start a Render service without relying on shell command parsing."""

from __future__ import annotations

import os
import subprocess
import sys
from ipaddress import IPv4Address


def _run(*command: str) -> None:
    subprocess.run(command, check=True)


def _exec(*command: str) -> None:
    os.execvp(command[0], command)


def main() -> None:
    service = sys.argv[1] if len(sys.argv) == 2 else ""
    port = os.getenv("PORT", "10000")
    bind_host = os.getenv("RENDER_BIND_HOST", str(IPv4Address(0)))

    if service == "api":
        from src.storage.schema_migrations import apply_migrations

        print(apply_migrations(), flush=True)
        _exec("uvicorn", "app.main:app", "--host", bind_host, "--port", port)
    elif service == "assistant":
        _run(sys.executable, "-m", "assistant_api.cli", "migrate")
        _exec(
            "uvicorn",
            "assistant_api.main:app",
            "--host",
            bind_host,
            "--port",
            port,
        )
    elif service == "django":
        _run(sys.executable, "web/manage.py", "migrate", "--noinput")
        _run(sys.executable, "web/manage.py", "collectstatic", "--noinput")
        _exec(
            "gunicorn",
            "web.config.wsgi:application",
            "--bind",
            f"{bind_host}:{port}",
        )
    elif service == "streamlit":
        _exec(
            "streamlit",
            "run",
            "app.py",
            "--server.address",
            bind_host,
            "--server.port",
            port,
            "--server.headless",
            "true",
        )
    else:
        raise SystemExit("Usage: python -m src.render_start api|assistant|django|streamlit")


if __name__ == "__main__":
    main()
