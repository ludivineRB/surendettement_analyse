"""Backward-compatible offline entry point for the autonomous benchmark."""

from __future__ import annotations

from benchmark.llm_benchmark import main as llm_main


def main(argv: list[str] | None = None) -> int:
    return llm_main(["--provider", "fixture", *(argv or [])])


if __name__ == "__main__":
    raise SystemExit(main())
