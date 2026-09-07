"""Small JSON formatter for operational logs."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import re


_SECRET = re.compile(
    r"(?i)(password|token|secret|authorization)(\s*[=:]\s*)([^\s,;]+)"
)


class JSONFormatter(logging.Formatter):
    fields = (
        "request_id",
        "http_method",
        "http_path",
        "http_status",
        "duration_ms",
    )

    def format(self, record):
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": _redact(record.getMessage()),
        }
        for field in self.fields:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = _redact(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False)


def _redact(value: str) -> str:
    """Mask common credentials before operational logs leave the process."""
    return _SECRET.sub(r"\1\2[REDACTED]", value)
