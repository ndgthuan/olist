"""Integration test: needs the Postgres from compose.yaml running.

Skipped (not failed) when the database is not reachable.
"""

import os

import psycopg
import pytest
from psycopg import sql

from pipeline.db import get_connection
from pipeline.load_raw import TABLES, main

# Give up after 3 s instead of hanging when Docker is off.
os.environ.setdefault("PGCONNECT_TIMEOUT", "3")

EXPECTED_ROWS = {
    "customers": 99_441,
    "sellers": 3_095,
    "products": 32_951,
    "product_category_name_translation": 71,
    "geolocation": 1_000_163,
    "orders": 99_441,
    "order_items": 112_650,
    "order_payments": 103_886,
    "order_reviews": 99_224,
}


def db_is_up() -> bool:
    try:
        get_connection().close()
    except psycopg.OperationalError:
        return False
    return True


pytestmark = pytest.mark.skipif(not db_is_up(), reason="Postgres not running (docker compose up -d)")


def count_rows() -> dict[str, int]:
    counts = {}
    with get_connection() as conn:
        for table, _ in TABLES:
            query = sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier("raw", table))
            counts[table] = conn.execute(query).fetchone()[0]
    return counts


def test_load_raw_twice_gives_same_counts():
    main()
    first = count_rows()
    main()
    second = count_rows()

    assert first == second  # idempotent: run 2 changes nothing
    assert first == EXPECTED_ROWS  # correct: every table has the real row count
