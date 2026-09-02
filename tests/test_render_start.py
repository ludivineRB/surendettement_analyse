from unittest.mock import call, patch

import pytest

from src import render_start


@pytest.mark.parametrize(
    ("service", "executable"),
    [
        ("api", "uvicorn"),
        ("assistant", "uvicorn"),
        ("django", "gunicorn"),
        ("streamlit", "streamlit"),
    ],
)
@patch("src.render_start.os.execvp")
@patch("src.render_start.subprocess.run")
def test_render_service_launcher_uses_port(
    run, execvp, service, executable, monkeypatch
):
    monkeypatch.setenv("PORT", "12345")
    monkeypatch.setenv("RENDER_BIND_HOST", "0.0.0.0")
    monkeypatch.setattr(render_start.sys, "argv", ["render_start", service])
    if service == "api":
        monkeypatch.setattr(
            "src.storage.schema_migrations.apply_migrations", lambda: {"status": "ok"}
        )

    render_start.main()

    assert execvp.call_args.args[0] == executable
    assert any("0.0.0.0" in argument for argument in execvp.call_args.args[1])
    assert any("12345" in argument for argument in execvp.call_args.args[1])
    if service == "django":
        assert run.call_args_list == [
            call(
                (
                    render_start.sys.executable,
                    "web/manage.py",
                    "migrate",
                    "--noinput",
                ),
                check=True,
            ),
            call(
                (
                    render_start.sys.executable,
                    "web/manage.py",
                    "collectstatic",
                    "--noinput",
                ),
                check=True,
            ),
        ]
