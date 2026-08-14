from unittest.mock import Mock, patch

from assistant_api.cli import migrate
from assistant_api.migrations import MigrationReport


@patch("assistant_api.cli.apply_migrations")
@patch("assistant_api.cli.get_engine")
def test_migrate_reports_applied_versions(get_engine, apply_migrations):
    engine = Mock()
    get_engine.return_value = engine
    apply_migrations.return_value = MigrationReport(
        applied=("001_corpus_chunks",),
        already_applied=(),
    )

    assert migrate() == {
        "applied": ["001_corpus_chunks"],
        "already_applied": [],
    }
    apply_migrations.assert_called_once_with(engine)
