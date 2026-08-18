"""Settings for the standalone Django web service."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import unquote, urlparse

from django.core.exceptions import ImproperlyConfigured


WEB_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = WEB_ROOT.parent


def required_setting(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ImproperlyConfigured(f"{name} must be configured")
    return value


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}


def postgres_database_config(url: str) -> dict:
    parsed = urlparse(url)
    if parsed.scheme not in {"postgresql", "postgresql+psycopg"}:
        raise ImproperlyConfigured("DATABASE_URL must use PostgreSQL")
    if not parsed.hostname or not parsed.path.lstrip("/"):
        raise ImproperlyConfigured("DATABASE_URL is incomplete")
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": parsed.path.lstrip("/"),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname,
        "PORT": parsed.port or 5432,
        "CONN_MAX_AGE": int(os.getenv("DJANGO_DB_CONN_MAX_AGE", "60")),
    }


SECRET_KEY = required_setting("DJANGO_SECRET_KEY")
DEBUG = env_bool("DJANGO_DEBUG")
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "web.accounts",
    "web.dashboard",
    "web.analytics",
    "web.assistant",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "web.config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [WEB_ROOT / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]
WSGI_APPLICATION = "web.config.wsgi.application"

DATABASES = {
    "default": postgres_database_config(required_setting("DATABASE_URL")),
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        )
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation.MinimumLengthValidator"
        )
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation.CommonPasswordValidator"
        )
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation.NumericPasswordValidator"
        )
    },
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [WEB_ROOT / "static"]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "home"

SESSION_COOKIE_SECURE = env_bool("DJANGO_SECURE_COOKIES")
CSRF_COOKIE_SECURE = env_bool("DJANGO_SECURE_COOKIES")
SECURE_PROXY_SSL_HEADER = (
    ("HTTP_X_FORWARDED_PROTO", "https")
    if env_bool("DJANGO_TRUST_PROXY_HEADERS")
    else None
)

ANALYTICS_API_BASE_URL = os.getenv(
    "ANALYTICS_API_BASE_URL",
    "http://127.0.0.1:8020",
)
ANALYTICS_API_TIMEOUT_SECONDS = float(
    os.getenv("ANALYTICS_API_TIMEOUT_SECONDS", "5")
)

ASSISTANT_API_BASE_URL = os.getenv(
    "ASSISTANT_API_BASE_URL",
    "http://127.0.0.1:8030",
)
ASSISTANT_API_TIMEOUT_SECONDS = float(
    os.getenv("ASSISTANT_API_TIMEOUT_SECONDS", "90")
)
