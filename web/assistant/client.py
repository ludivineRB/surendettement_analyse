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
        configured_url = (
            base_url or settings.ASSISTANT_API_BASE_URL
        )
        if "://" not in configured_url:
            configured_url = f"http://{configured_url}"
        self.base_url = configured_url.rstrip("/")
        self.timeout = timeout or settings.ASSISTANT_API_TIMEOUT_SECONDS
        self.session = session or requests.Session()

    def answer(
        self,
        question: str,
        *,
        mode: str = "information",
        actor_id: str | None = None,
        conversation_id=None,
    ) -> dict:
        payload = {"question": question, "mode": mode}
        if actor_id:
            payload["actor_id"] = actor_id
        if conversation_id:
            payload["conversation_id"] = str(conversation_id)
        try:
            headers = {"Accept": "application/json"}
            headers["X-Internal-Token"] = settings.ASSISTANT_INTERNAL_TOKEN
            response = self.session.post(
                f"{self.base_url}/v1/answers",
                json=payload,
                timeout=self.timeout,
                headers=headers,
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
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else 0
            if status in {401, 403}:
                message = "L’accès au service assistant n’est pas autorisé."
            elif 400 <= status < 500:
                message = "La demande n’a pas été acceptée par l’assistant."
            else:
                message = "L’assistant est temporairement indisponible."
            logger.warning("Assistant API returned HTTP status %s", status)
            raise AssistantAPIError(message) from exc
        except requests.RequestException as exc:
            logger.warning("Assistant API request failed")
            raise AssistantAPIError(
                "L’assistant est temporairement indisponible."
            ) from exc
