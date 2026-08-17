"""Provider-neutral grounded answer generation."""

from __future__ import annotations

import json
from typing import Protocol

from assistant_api.orchestration import GroundingContext


class InsufficientGrounding(RuntimeError):
    """Raised when no approved evidence can support an answer."""


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
    system_prompt = (
        "Tu es un assistant métier sur le surendettement en France. "
        "Réponds uniquement à partir des preuves fournies. "
        "Distingue constat statistique et interprétation. "
        "N'invente jamais une causalité, une valeur ou une source. "
        "Cite les documents avec [S1], [S2] et les données avec [D1], [D2]. "
        "Si les preuves sont insuffisantes, indique-le explicitement."
    )
    user_prompt = json.dumps(
        {
            "question": question,
            "method": context.method,
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
    return generator.generate(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    ).strip()
