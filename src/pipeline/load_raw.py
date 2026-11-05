import logging
import time
from pathlib import Path

import psycopg

from pipeline.db import get_connection

PROJECT_DIR = Path(__file__).resolve().parents[2]
OLIST_DIR = PROJECT_DIR / "data" / "raw" / "olist"
LOG_DIR = PROJECT_DIR / "logs"
LOG_FILE = LOG_DIR / "load_raw.log"
CUSTOMERS_FILE = OLIST_DIR / "olist_customers_dataset.csv"
CHUNK_SIZE = 1024 * 1024
logger = logging.getLogger(__name__)


def load_customers(conn: psycopg.Connection, csv_path: Path) -> int:
    copy_sql = "COPY raw.customers FROM STDIN WITH (FORMAT csv, HEADER true)"
    with conn.cursor() as cur:
        with cur.copy(copy_sql) as copy, open(csv_path, "rb") as f:
            while data := f.read(CHUNK_SIZE):
                copy.write(data)
        row_count = cur.execute("SELECT count(*) FROM raw.customers").fetchone()[0]
    return row_count


def main() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                        encoding="utf-8", level=logging.INFO, filename=LOG_FILE)
    try:
        started = time.perf_counter()
        with get_connection() as conn:
            row_count = load_customers(conn, CUSTOMERS_FILE)
        logger.info("raw.customers rows: %d", row_count)
        logger.info("duration_ms= %.0f", (time.perf_counter() - started) * 1000)
    except Exception:
        logger.exception("load_raw failed")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
