from pathlib import Path

import pytest

from cli import execute, table_names, validate_read_only
from init_db import initialize


CASES = [
    (
        "Quels sont les 5 clients qui ont dépensé le plus cette année ?",
        """SELECT c.name, ROUND(SUM(p.price * o.quantity), 2) AS total_spent
        FROM customers c JOIN orders o ON o.customer_id = c.id
        JOIN products p ON p.id = o.product_id
        WHERE o.status = 'paid' AND strftime('%Y', o.order_date) = '2026'
        GROUP BY c.id, c.name ORDER BY total_spent DESC LIMIT 5""",
        [("Alice Martin", 1500.0), ("Benoît Dupont", 1300.0), ("Emma Roux", 1000.0),
         ("David Leroy", 900.0), ("Chloé Bernard", 500.0)],
    ),
    (
        "Donne-moi le chiffre d'affaires total par mois.",
        """SELECT strftime('%Y-%m', o.order_date) AS month,
        ROUND(SUM(p.price * o.quantity), 2) AS revenue
        FROM orders o JOIN products p ON p.id = o.product_id
        WHERE o.status = 'paid' GROUP BY month ORDER BY month""",
        [("2025-12", 600.0), ("2026-01", 1900.0), ("2026-02", 800.0),
         ("2026-03", 900.0), ("2026-04", 950.0), ("2026-05", 1000.0)],
    ),
    (
        "Quelle catégorie génère le plus de chiffre d'affaires en 2026 ?",
        """SELECT p.category, ROUND(SUM(p.price * o.quantity), 2) AS revenue
        FROM orders o JOIN products p ON p.id = o.product_id
        WHERE o.status = 'paid' AND strftime('%Y', o.order_date) = '2026'
        GROUP BY p.category ORDER BY revenue DESC LIMIT 1""",
        [("Mobilier", 2400.0)],
    ),
    (
        "Combien de commandes payées avons-nous par ville ?",
        """SELECT c.city, COUNT(*) AS paid_orders FROM customers c
        JOIN orders o ON o.customer_id = c.id WHERE o.status = 'paid'
        GROUP BY c.city ORDER BY paid_orders DESC, c.city""",
        [("Paris", 3), ("Lyon", 2), ("Bordeaux", 2), ("Lille", 1), ("Marseille", 1)],
    ),
    (
        "Quel est le panier moyen des commandes payées en 2026 ?",
        """WITH totals AS (
        SELECT o.id, SUM(p.price * o.quantity) AS amount FROM orders o
        JOIN products p ON p.id = o.product_id
        WHERE o.status = 'paid' AND strftime('%Y', o.order_date) = '2026'
        GROUP BY o.id) SELECT ROUND(AVG(amount), 2) AS average_basket FROM totals""",
        [(693.75,)],
    ),
]


@pytest.fixture()
def database(tmp_path: Path) -> Path:
    return initialize(tmp_path / "shop.db")


def test_table_names_come_from_sqlite_catalog(database: Path) -> None:
    assert table_names(database) == {"customers", "orders", "products"}


@pytest.mark.parametrize(("question", "sql", "expected"), CASES)
def test_reference_queries(database: Path, question: str, sql: str, expected: list[tuple]) -> None:
    validate_read_only(sql, {"customers", "orders", "products", "totals"})
    assert execute(database, sql)[1] == expected


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM orders",
        "SELECT * FROM customers; DROP TABLE customers",
        "WITH gone AS (DELETE FROM orders RETURNING *) SELECT * FROM gone",
        "SELECT * FROM secrets",
    ],
)
def test_unsafe_sql_is_rejected(sql: str) -> None:
    with pytest.raises(Exception):
        validate_read_only(sql, {"customers", "orders", "products"})
