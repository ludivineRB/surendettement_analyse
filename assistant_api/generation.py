"""Provider-neutral grounded answer generation."""

from __future__ import annotations

import json
import re
from typing import Protocol

from assistant_api.orchestration import GroundingContext


class InsufficientGrounding(RuntimeError):
    """Raised when no approved evidence can support an answer."""


class InvalidCitation(InsufficientGrounding):
    """Raised when generated text references evidence that was not supplied."""


class GeneratorUnavailable(RuntimeError):
    """Raised when no text-generation provider is configured."""


class TextGenerator(Protocol):
    def generate(self, *, system_prompt: str, user_prompt: str) -> str: ...


class UnconfiguredGenerator:
    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        raise GeneratorUnavailable("generator_not_configured")


def generate_grounded_answer(
    question: str,
    context: GroundingContext,
    generator: TextGenerator,
) -> str:
    if not context.documentary_chunks and not context.analytics_rows:
        raise InsufficientGrounding(
            "Aucune source approuvée ne permet de répondre."
        )
    allowed_document_citations = [
        f"S{index}"
        for index in range(1, len(context.documentary_chunks) + 1)
    ]
    allowed_data_citations = [
        f"D{index}" for index in range(1, len(context.analytics_rows[:100]) + 1)
    ]
    system_prompt = (
        "Tu es un assistant métier sur le surendettement en France. "
        "Réponds uniquement à partir des preuves fournies. "
        "Distingue constat statistique et interprétation. "
        "N'invente jamais une causalité, une valeur ou une source. "
        "Utilise uniquement les identifiants de citation explicitement autorisés. "
        "N'utilise jamais une citation [D...] si aucune donnée analytique "
        "n'est fournie. "
        "Si les preuves sont insuffisantes, indique-le explicitement."
        "Pour une analyse SQL, le SQL fourni a déjà été validé et exécuté. "
        "Tu peux décrire ce que démontrent ses opérations de classement, "
        "d'agrégation et de filtrage, sans extrapoler au-delà de leur périmètre."
    )
    user_prompt = json.dumps(
        {
            "question": question,
            "method": context.method,
            "validated_analytical_sql": context.analytical_sql,
            "analytical_intent": (
                context.analytical_intent.model_dump(mode="json")
                if context.analytical_intent
                else None
            ),
            "allowed_citations": {
                "documents": allowed_document_citations,
                "analytics": allowed_data_citations,
            },
            "documentary_evidence": [
                {
                    "citation": f"S{index}",
                    "title": chunk["source_title"],
                    "publisher": chunk["publisher"],
                    "period": chunk["reference_period"],
                    "section": chunk["section"],
                    "content": chunk["content"],
                }
                for index, chunk in enumerate(
                    context.documentary_chunks,
                    start=1,
                )
            ],
            "analytical_evidence": [
                {"citation": f"D{index}", **row}
                for index, row in enumerate(
                    context.analytics_rows[:100],
                    start=1,
                )
            ],
        },
        ensure_ascii=False,
        default=str,
    )
    answer = generator.generate(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    ).strip()
    _validate_citations(
        answer,
        allowed={*allowed_document_citations, *allowed_data_citations},
    )
    return answer


def _validate_citations(answer: str, *, allowed: set[str]) -> None:
    cited = set(re.findall(r"\[([SD]\d+)\]", answer))
    invalid = cited - allowed
    if invalid:
        raise InvalidCitation(
            f"Références non autorisées: {', '.join(sorted(invalid))}"
        )
    if allowed and not cited:
        raise InvalidCitation("La réponse ne contient aucune citation")
