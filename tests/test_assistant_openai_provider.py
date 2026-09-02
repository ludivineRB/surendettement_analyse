from unittest.mock import Mock, patch

import pytest

from assistant_api.generation import GeneratorUnavailable, UnconfiguredGenerator
from assistant_api.openai_provider import (
    OpenAIResponsesGenerator,
    get_text_generator,
)


@patch("assistant_api.openai_provider.requests.post")
def test_responses_adapter_uses_instructions_and_extracts_text(post):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "output": [
            {
                "type": "message",
                "content": [
                    {"type": "output_text", "text": "Réponse [S1]"}
                ],
            }
        ]
    }
    post.return_value = response
    generator = OpenAIResponsesGenerator(api_key="test-key")

    answer = generator.generate(
        system_prompt="Consignes",
        user_prompt="Preuves",
    )

    assert answer == "Réponse [S1]"
    request = post.call_args.kwargs
    assert request["json"]["instructions"] == "Consignes"
    assert request["json"]["input"] == "Preuves"
    assert request["headers"]["Authorization"] == "Bearer test-key"


def test_generator_is_unconfigured_without_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    assert isinstance(get_text_generator(), UnconfiguredGenerator)


@patch("assistant_api.openai_provider.requests.post")
def test_provider_logs_only_normalized_error(post, caplog):
    response = Mock()
    response.ok = False
    response.json.return_value = {
        "error": {
            "code": "insufficient_quota",
            "message": "secret remote body",
        }
    }
    response.status_code = 429
    post.return_value = response
    generator = OpenAIResponsesGenerator(api_key="test-key")

    with pytest.raises(
        GeneratorUnavailable,
        match="^openai_insufficient_quota$",
    ):
        generator.generate(system_prompt="System", user_prompt="User")

    assert "status=429 reason=openai_insufficient_quota" in caplog.text
    assert "secret remote body" not in caplog.text
