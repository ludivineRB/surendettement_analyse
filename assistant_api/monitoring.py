"""Metrics dedicated to RAG and read-only SQL operations."""

from __future__ import annotations

from collections import defaultdict
from threading import Lock


class AssistantMetrics:
    def __init__(self) -> None:
        self._values: defaultdict[
            tuple[str, tuple[tuple[str, str], ...]], float
        ] = defaultdict(float)
        self._lock = Lock()

    def increment(self, name: str, **labels: str) -> None:
        key = (name, tuple(sorted((key, str(value)) for key, value in labels.items())))
        with self._lock:
            self._values[key] += 1

    def observe(self, name: str, value: float, **labels: str) -> None:
        with self._lock:
            label_values = tuple(sorted((key, str(val)) for key, val in labels.items()))
            self._values[(name + "_count", label_values)] += 1
            self._values[(name + "_sum", label_values)] += value

    def render(self) -> str:
        with self._lock:
            values = sorted(self._values.items())
        lines = []
        for (name, labels), value in values:
            suffix = ""
            if labels:
                suffix = "{" + ",".join(
                    f'{key}="{val.replace(chr(34), chr(92) + chr(34))}"'
                    for key, val in labels
                ) + "}"
            lines.append(f"{name}{suffix} {value:g}")
        return "\n".join(lines) + "\n"


metrics = AssistantMetrics()
