import json

import pytest

from assistant_api.corpus import (
    CorpusRegistryError,
    default_registry_path,
    load_registry,
)


def test_default_registry_contains_only_curated_official_sources():
    registry = load_registry(default_registry_path())

    assert len(registry.sources) == 6
    assert {source.publisher for source in registry.sources} == {
        "Banque de France",
        "Insee",
    }
    assert all(source.content_sha256 for source in registry.sources)
    assert all(source.normalized_characters >= 50 for source in registry.sources)


def test_registry_refuses_unofficial_host(tmp_path):
    payload = json.loads(default_registry_path().read_text(encoding="utf-8"))
    payload["sources"][0]["url"] = "https://example.org/untrusted"
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(CorpusRegistryError, match="Unofficial"):
        load_registry(registry_path)
