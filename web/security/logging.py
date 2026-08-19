"""Small JSON formatter for operational logs."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging


class JSONFormatter(logging.Formatter):
    fields = (
        "request_id",
        "http_method",
        "http_path",
        "http_status",
        "duration_ms",
        "actor_id",
    )

    def format(self, record):
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in self.fields:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)
