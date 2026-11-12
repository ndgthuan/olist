import logging
import time
from pathlib import Path

import psycopg
from psycopg import sql

from pipeline.db import get_connection

PROJECT_DIR = Path(__file__).resolve().parents[2]
OLIST_DIR = PROJECT_DIR / "data" / "raw" / "olist"
LOG_DIR = PROJECT_DIR / "logs"
LOG_FILE = LOG_DIR / "load_raw.log"
CHUNK_SIZE = 1024 * 1024

# Load order matters: parents before children (FKs).
TABLES = [
    ("customers", "olist_customers_dataset.csv"),
    ("sellers", "olist_sellers_dataset.csv"),
    ("products", "olist_products_dataset.csv"),
    ("product_category_name_translation", "product_category_name_translation.csv"),
    ("geolocation", "olist_geolocation_dataset.csv"),
    ("orders", "olist_orders_dataset.csv"),
    ("order_items", "olist_order_items_dataset.csv"),
    ("order_payments", "olist_order_payments_dataset.csv"),
    ("order_reviews", "olist_order_reviews_dataset.csv"),
]
logger = logging.getLogger(__name__)


def load_table(conn: psycopg.Connection, table: str, csv_path: Path) -> int:
    target = sql.Identifier("raw", table)
    copy_sql = sql.SQL(
        "COPY {} FROM STDIN WITH (FORMAT csv, HEADER true)").format(target)
    count_sql = sql.SQL("SELECT count(*) FROM {}").format(target)
    with conn.cursor() as cur:
        with cur.copy(copy_sql) as copy, open(csv_path, "rb") as f:
            while data := f.read(CHUNK_SIZE):
                copy.write(data)
        row_count = cur.execute(count_sql).fetchone()[0]
    return row_count


def truncate_all(conn: psycopg.Connection) -> None:
    targets = sql.SQL(", ").join(sql.Identifier("raw", table)
                                 for table, _ in TABLES)
    conn.execute(sql.SQL("TRUNCATE {}").format(targets))


def main() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                        encoding="utf-8", level=logging.INFO, filename=LOG_FILE)
    try:
        started = time.perf_counter()
        with get_connection() as conn:
            truncate_all(conn)
            for table, filename in TABLES:
                row_count = load_table(conn, table, OLIST_DIR / filename)
                logger.info("raw.%s rows: %d", table, row_count)
        logger.info("duration_ms= %.0f",
                    (time.perf_counter() - started) * 1000)
    except Exception:
        logger.exception("load_raw failed")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
