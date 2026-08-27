"""Create a tiny deterministic SQLite shop database."""

from pathlib import Path
import sqlite3


DB_PATH = Path(__file__).with_name("shop.db")

SCHEMA = """
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    city TEXT NOT NULL,
    signup_date TEXT NOT NULL
);
CREATE TABLE products (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    price REAL NOT NULL
);
CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    order_date TEXT NOT NULL,
    status TEXT NOT NULL
);
"""

CUSTOMERS = [
    (1, "Alice Martin", "Paris", "2024-01-12"),
    (2, "Benoît Dupont", "Lyon", "2024-03-05"),
    (3, "Chloé Bernard", "Bordeaux", "2025-02-18"),
    (4, "David Leroy", "Lille", "2025-06-22"),
    (5, "Emma Roux", "Paris", "2025-09-10"),
    (6, "Farid Moreau", "Marseille", "2026-01-08"),
]
PRODUCTS = [
    (1, "Ordinateur portable", "Informatique", 1200.0),
    (2, "Écran 27 pouces", "Informatique", 350.0),
    (3, "Bureau", "Mobilier", 500.0),
    (4, "Chaise ergonomique", "Mobilier", 300.0),
    (5, "Casque audio", "Accessoires", 150.0),
]
ORDERS = [
    (1, 1, 1, 1, "2026-01-15", "paid"),
    (2, 2, 2, 2, "2026-01-28", "paid"),
    (3, 3, 3, 1, "2026-02-10", "paid"),
    (4, 1, 5, 2, "2026-02-21", "paid"),
    (5, 4, 4, 3, "2026-03-08", "paid"),
    (6, 5, 1, 1, "2026-03-19", "cancelled"),
    (7, 6, 2, 1, "2026-04-02", "paid"),
    (8, 2, 5, 4, "2026-04-17", "paid"),
    (9, 3, 4, 2, "2025-12-12", "paid"),
    (10, 5, 3, 2, "2026-05-06", "paid"),
]


def initialize(path: Path = DB_PATH) -> Path:
    with sqlite3.connect(path) as connection:
        connection.executescript(SCHEMA)
        connection.executemany("INSERT INTO customers VALUES (?, ?, ?, ?)", CUSTOMERS)
        connection.executemany("INSERT INTO products VALUES (?, ?, ?, ?)", PRODUCTS)
        connection.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?)", ORDERS)
    return path


if __name__ == "__main__":
    print(f"Base créée : {initialize()}")
