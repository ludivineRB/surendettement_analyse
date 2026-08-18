import json
from unittest.mock import Mock

import pytest

from assistant_api.generation import (
    InvalidCitation,
    InsufficientGrounding,
    generate_grounded_answer,
)
from assistant_api.orchestration import GroundingContext


def test_generation_labels_sources_and_data_without_mixing_them():
    generator = Mock()
    generator.generate.return_value = "Réponse fondée [S1] [D1]"
    context = GroundingContext(
        method="hybrid",
        documentary_chunks=[
            {
                "source_title": "Étude",
                "publisher": "Banque de France",
                "reference_period": "2025",
                "section": "Synthèse",
                "content": "Contenu approuvé",
            }
        ],
        analytics_dataset="surendettement",
        analytics_rows=[{"reference_year": 2025, "value": 42}],
    )

    answer = generate_grounded_answer("Question", context, generator)

    assert answer == "Réponse fondée [S1] [D1]"
    prompt = json.loads(generator.generate.call_args.kwargs["user_prompt"])
    assert prompt["documentary_evidence"][0]["citation"] == "S1"
    assert prompt["analytical_evidence"][0]["citation"] == "D1"


def test_generation_refuses_to_answer_without_evidence():
    context = GroundingContext("documents", [], None, [])

    with pytest.raises(InsufficientGrounding):
        generate_grounded_answer("Question", context, Mock())


def test_generation_rejects_a_data_citation_without_analytics():
    generator = Mock()
    generator.generate.return_value = "Affirmation [S1] [D1]"
    context = GroundingContext(
        method="documents",
        documentary_chunks=[
            {
                "source_title": "Définition",
                "publisher": "Insee",
                "reference_period": "2026",
                "section": "Définition",
                "content": "Contenu officiel",
            }
        ],
        analytics_dataset=None,
        analytics_rows=[],
    )

    with pytest.raises(InvalidCitation, match="D1"):
        generate_grounded_answer("Question", context, generator)
