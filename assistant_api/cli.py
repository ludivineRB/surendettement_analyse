"""Administrative commands for Assistant API storage and indexing."""

from __future__ import annotations

import argparse
import json

from assistant_api.corpus import default_registry_path, load_registry
from assistant_api.indexing import prepare_registry_chunks
from assistant_api.migrations import apply_migrations
from assistant_api.repository import replace_active_corpus
from assistant_api.storage import get_engine


def migrate() -> dict:
    report = apply_migrations(get_engine())
    return {
        "applied": list(report.applied),
        "already_applied": list(report.already_applied),
    }


def index() -> dict:
    engine = get_engine()
    apply_migrations(engine)
    registry = load_registry(default_registry_path())
    chunks = prepare_registry_chunks(registry)
    indexed = replace_active_corpus(engine, chunks)
    return {
        "status": "indexed",
        "sources": len(registry.sources),
        "chunks": indexed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("migrate", "index"))
    arguments = parser.parse_args()
    result = migrate() if arguments.command == "migrate" else index()
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
