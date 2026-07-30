import pytest

from assistant_api.routing import route_question


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("Que signifie la capacité de remboursement ?", "documents"),
        (
            "Quelle est l'évolution du surendettement en France en 2024 ?",
            "analytics",
        ),
        (
            "Pourquoi le taux augmente-t-il dans ce département ?",
            "hybrid",
        ),
    ],
)
def test_route_question(question, expected):
    assert route_question(question) == expected
