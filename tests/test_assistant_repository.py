from unittest.mock import Mock

import pytest

from assistant_api.chunking import CorpusChunk
from assistant_api.repository import EmptyCorpusError, replace_active_corpus


def test_replace_corpus_refuses_empty_input():
    with pytest.raises(EmptyCorpusError):
        replace_active_corpus(Mock(), [])


def test_replace_corpus_is_one_transaction():
    connection = Mock()
    transaction = Mock()
    transaction.__enter__ = Mock(return_value=connection)
    transaction.__exit__ = Mock(return_value=False)
    engine = Mock()
    engine.begin.return_value = transaction
    chunk = CorpusChunk(
        chunk_id="a" * 64,
        source_id="insee-test",
        source_url="https://www.insee.fr/fr/test",
        source_title="Définition",
        publisher="Insee",
        reference_period="2026",
        geographic_scope="France",
        source_sha256="b" * 64,
        section="Définition",
        ordinal=0,
        content="Contenu",
        content_sha256="c" * 64,
    )

    assert replace_active_corpus(engine, [chunk]) == 1
    assert connection.execute.call_count == 2
