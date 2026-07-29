import json

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from src.pipeline_orchestrator import refresh_all
from src.storage.models import Base, PipelineRun


def test_orchestrator_persists_successful_steps(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'pipeline.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(
        "src.pipeline_orchestrator.get_session_factory", lambda: factory
    )
    monkeypatch.setattr("src.pipeline_orchestrator.init_db", lambda: None)
    monkeypatch.setattr(
        "src.pipeline_orchestrator.run_quality_gates",
        lambda: {"passed": True, "checks": {}},
    )
    result = refresh_all(
        from_period="2026-01",
        steps=[("first", lambda: {"inserted": 1})],
    )
    assert result["status"] == "success"
    with factory() as session:
        run = session.execute(select(PipelineRun)).scalar_one()
        assert run.status == "success"
        assert json.loads(run.step_results_json)["first"]["inserted"] == 1
