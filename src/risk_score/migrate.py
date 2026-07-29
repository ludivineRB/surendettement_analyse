"""Schema migration and initial model seed without an external migration tool."""

from __future__ import annotations

import json
from pathlib import Path

from src.risk_score.config import seed_default_model, seed_model_1_1, seed_model_1_2
from src.storage.database import get_session_factory, init_db


def migrate_and_seed(mapping_path: Path | None = None) -> dict:
    """Create missing tables/indexes and seed the default model idempotently."""
    mapping = {}
    if mapping_path:
        payload = json.loads(mapping_path.read_text(encoding="utf-8"))
        mapping = payload.get("indicator_mapping", payload)
        if not isinstance(mapping, dict):
            raise ValueError("The indicator mapping must be a JSON object")
    init_db()
    factory = get_session_factory()
    with factory() as session:
        legacy_report = seed_default_model(session, mapping=mapping)
        bridge_report = seed_model_1_1(session)
        report = seed_model_1_2(session)
        report["previous_model"] = bridge_report
        report["legacy_model"] = legacy_report
        session.commit()
    return report
