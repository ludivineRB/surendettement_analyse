"""OpenAI Responses API adapter for grounded text generation."""

from __future__ import annotations

import os

import requests

from assistant_api.generation import (
    GeneratorUnavailable,
    TextGenerator,
    UnconfiguredGenerator,
)


class OpenAIResponsesGenerator:
    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gpt-5.6-terra",
        timeout_seconds: float = 60,
    ) -> None:
        if not api_key.strip():
            raise GeneratorUnavailable("openai_api_key_missing")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        try:
            response = requests.post(
                "https://api.openai.com/v1/responses",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "instructions": system_prompt,
                    "input": user_prompt,
                    "reasoning": {"effort": "low"},
                    "max_output_tokens": 1_200,
                },
                timeout=self.timeout_seconds,
            )
            if not response.ok:
                raise GeneratorUnavailable(_safe_error_code(response))
            response.raise_for_status()
            payload = response.json()
        except GeneratorUnavailable:
            raise
        except (requests.RequestException, ValueError) as exc:
            raise GeneratorUnavailable("openai_request_failed") from exc
        output_text = _extract_output_text(payload)
        if not output_text:
            raise GeneratorUnavailable("openai_response_has_no_text")
        return output_text


def get_text_generator() -> TextGenerator:
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return UnconfiguredGenerator()
    return OpenAIResponsesGenerator(
        api_key=api_key,
        model=os.getenv("OPENAI_MODEL", "gpt-5.6-terra"),
    )


def _extract_output_text(payload: dict) -> str:
    texts: list[str] = []
    for item in payload.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                texts.append(content["text"])
    return "\n".join(texts).strip()


def _safe_error_code(response: requests.Response) -> str:
    try:
        remote_code = response.json().get("error", {}).get("code")
    except ValueError:
        remote_code = None
    allowed_codes = {
        "insufficient_quota": "openai_insufficient_quota",
        "invalid_api_key": "openai_invalid_api_key",
        "model_not_found": "openai_model_not_available",
    }
    return allowed_codes.get(remote_code, "openai_request_failed")
