"""Dependency-free Prometheus metrics and structured request logging."""

from __future__ import annotations

from collections import Counter
from threading import Lock


class Metrics:
    def __init__(self) -> None:
        self._values: Counter[tuple[str, tuple[tuple[str, str], ...]]] = Counter()
        self._lock = Lock()

    def increment(self, name: str, **labels: str) -> None:
        key = (name, tuple(sorted((key, str(value)) for key, value in labels.items())))
        with self._lock:
            self._values[key] += 1

    def observe(self, name: str, value: float, **labels: str) -> None:
        key_labels = {**labels}
        with self._lock:
            for suffix, amount in (("_count", 1), ("_sum", value)):
                key = (name + suffix, tuple(sorted(key_labels.items())))
                self._values[key] += amount

    def render(self) -> str:
        lines = []
        with self._lock:
            values = sorted(self._values.items())
        for (name, labels), value in values:
            label_text = ""
            if labels:
                encoded = ",".join(f'{key}="{_escape(val)}"' for key, val in labels)
                label_text = "{" + encoded + "}"
            lines.append(f"{name}{label_text} {value}")
        return "\n".join(lines) + "\n"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


metrics = Metrics()
