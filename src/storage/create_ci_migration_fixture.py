"""Create a minimal synthetic SQLite source for CI migration tests."""

from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.storage.models import Base, SurendettementData


def create_fixture(output: Path) -> Path:
    """Create a new fixture without ever replacing an existing database."""
    if output.exists():
        return output
    output.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{output}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            SurendettementData(
                year=2024,
                region="France",
                indicator="dossiers_deposes",
                value=1.0,
                source_file="synthetic-ci-fixture",
            )
        )
        session.commit()
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="create-ci-migration-fixture")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    print(create_fixture(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
