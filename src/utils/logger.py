"""Logging utilities shared across modules."""

from __future__ import annotations

import logging
import sys
import json
import re
from datetime import datetime, timezone

_SECRET = re.compile(r"(?i)(password|token|secret|authorization)(\s*[=:]\s*)([^\s,;]+)")


class JSONFormatter(logging.Formatter):
    """Structured formatter that masks common credential fields."""

    def format(self, record: logging.LogRecord) -> str:
        message = _SECRET.sub(r"\1\2[REDACTED]", record.getMessage())
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": message,
        }
        if record.exc_info:
            payload["exception"] = _SECRET.sub(
                r"\1\2[REDACTED]", self.formatException(record.exc_info)
            )
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging once for the project."""
    if logging.getLogger().handlers:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root = logging.getLogger()
    root.setLevel(level.upper())
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Return module logger."""
    return logging.getLogger(name)
