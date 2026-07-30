"""Pytest configuration shared by application tests."""


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "postgres_integration: tests requiring an explicit disposable PostgreSQL URL",
    )
