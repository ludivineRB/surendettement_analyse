"""HTTP boundary between Django and the standalone Assistant API."""

from __future__ import annotations

import logging

from django.conf import settings
import requests

from web.assistant.contracts import validate_answer


logger = logging.getLogger(__name__)


class AssistantAPIError(RuntimeError):
    """Stable UI-facing error for Assistant API failures."""


class AssistantClient:
    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
        session=None,
    ) -> None:
        self.base_url = (
            base_url or settings.ASSISTANT_API_BASE_URL
        ).rstrip("/")
        self.timeout = timeout or settings.ASSISTANT_API_TIMEOUT_SECONDS
        self.session = session or requests.Session()

    def answer(self, question: str, *, conversation_id=None) -> dict:
        payload = {"question": question}
        if conversation_id:
            payload["conversation_id"] = str(conversation_id)
        try:
            response = self.session.post(
                f"{self.base_url}/v1/answers",
                json=payload,
                timeout=self.timeout,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            return validate_answer(response.json())
        except requests.Timeout as exc:
            raise AssistantAPIError(
                "L’assistant met trop de temps à répondre."
            ) from exc
        except ValueError as exc:
            raise AssistantAPIError(
                "La réponse de l’assistant est invalide."
            ) from exc
        except requests.RequestException as exc:
            logger.warning("Assistant API request failed")
            raise AssistantAPIError(
                "L’assistant est temporairement indisponible."
            ) from exc
