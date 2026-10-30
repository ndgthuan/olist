from pathlib import Path
import logging
import requests
import time
import csv
from datetime import date, timedelta
from collections import Counter
import pyarrow as pa
import pyarrow.parquet as pq

URL = "https://api.frankfurter.dev/v2/rates"
BASE_CURRENCY = "BRL"
QUOTES = ["USD", "VND"]

PROJECT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
FX_DIR = RAW_DIR / "fx"
PROCESSED_DIR = DATA_DIR / "processed"
FX_RATE_FILE = PROCESSED_DIR / "fx_rates.csv"
ORDER_CLEAN_FILE = PROCESSED_DIR / "orders_clean.csv"
FX_RATE_PARQUET_FILE = PROCESSED_DIR / "fx_rates.parquet"
FX_SCHEMA = pa.schema([
    pa.field("date", pa.date32(), nullable=False),
    pa.field("quote", pa.string(), nullable=False),
    pa.field("rate", pa.float64(), nullable=False),
])
LOG_DIR = PROJECT_DIR / "logs"
LOG_FILE = LOG_DIR / "extract_fx.log"
OUTPUT_COLUMNS = ["date", "quote", "rate"]
logger = logging.getLogger(__name__)


class FxApiError(RuntimeError):
    def __init__(self, message, *, retryable):
        super().__init__(message)
        self.retryable = retryable


def fetch_rates(start: str, end: str, quotes: list) -> requests.Response:
    try:
        response = requests.get(
            url=URL, params={"quotes": ",".join(quotes), "base": BASE_CURRENCY, "from": start, "to": end}, timeout=(3.05, 30))
        response.raise_for_status()
        return response
    except requests.exceptions.HTTPError as e:
        code = e.response.status_code if e.response is not None else None
        retryable = code in {408, 425, 429} or (
            code is not None and 500 <= code <= 599)
        raise FxApiError(
            f"API returned {code}: {start} to {end}", retryable=retryable) from e
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
        raise FxApiError(
            f"Network failure: {start} to {end}", retryable=True) from e


def save_raw(response: requests.Response, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(response.content)
    tmp.replace(path)


def write_rates_csv(rows: list, path: Path) -> tuple[int, int]:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open(mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        skipped = 0
        written = 0
        for row in rows:
            if not isinstance(row.get("rate"), (int, float)):
                skipped += 1
                continue
            else:
                written += 1
                writer.writerow({
                    "date": row["date"],
                    "quote": row["quote"],
                    "rate": row["rate"]
                })
    tmp.replace(path)
    return skipped, written


def fetch_rates_with_retry(start: str, end: str, quotes: list, *, max_attempts=3, base_delay=1.0) -> requests.Response:
    for attempt in range(1, max_attempts + 1):
        try:
            return fetch_rates(start=start, end=end, quotes=quotes)
        except FxApiError as e:
            if not e.retryable or attempt == max_attempts:
                raise
            else:
                delay = base_delay * 2 ** (attempt - 1)
                logger.warning(
                    "Attempt %d/%d failed, retrying in %.1f s: %s", attempt, max_attempts, delay, e)
                time.sleep(delay)


def read_order_date_range(path: Path) -> tuple[str, str]:
    try:
        with path.open(mode="r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            dates = set()
            for row in reader:
                dates.add(row["order_purchase_timestamp"][:10])
    except FileNotFoundError as e:
        raise FileNotFoundError(f"Orders file not found : {path}. Run clean_orders first.") from e

    if not dates:
        raise ValueError(f"Empty file: {path}")
    return min(dates), max(dates)

def validate_rates(rows: list, quotes: list) -> None:
    if not isinstance(rows, list):
        raise ValueError("Response is not a list")
    if len(rows) == 0:
        raise ValueError("Response is empty")
    for row in rows:
        if row.get("quote") is None or row.get("date") is None:
            raise ValueError(f"Row is missing date or quote: {row}")
        if row["quote"] not in quotes:
            raise ValueError(f"Unexpected quote {row["quote"]!r} on {row["date"]}")

    count = Counter([row["quote"] for row in rows])
    logger.info("Rows per currency: %s", dict(count))
    date_by_quote = {}
    for q in quotes:
        date_by_quote[q] = {row["date"] for row in rows if row["quote"] == q}

    all_dates = set().union(*date_by_quote.values())

    for q, dates in date_by_quote.items():
        missing = sorted(all_dates - dates)
        if missing:
            logger.warning("%s has no rate for %d date(s): %s", q, len(missing), missing)

def write_rates_parquet(rows: list, path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    good_rows = []
    for row in rows:
        if not isinstance(row.get("rate"), (int, float)):
            continue
        good_rows.append({
            "date": date.fromisoformat(row["date"]),
            "quote": row["quote"],
            "rate": row["rate"],
        })
    table = pa.Table.from_pylist(good_rows, schema=FX_SCHEMA)
    pq.write_table(table=table, where=tmp)
    tmp.replace(path)
    return len(good_rows)

def main() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                        encoding="utf-8", level=logging.INFO, filename=LOG_FILE)
    try:
        started = time.perf_counter()
        first, last = read_order_date_range(path=ORDER_CLEAN_FILE)
        start = (date.fromisoformat(first) - timedelta(days=1)).isoformat()
        end = (date.fromisoformat(last) + timedelta(days=1)).isoformat()
        logger.info("fx range: %s to %s", start, end)

        response = fetch_rates_with_retry(start=start, end=end, quotes=QUOTES)
        rows = response.json()
        logger.info("Rows received: %d", len(rows))
        validate_rates(rows, QUOTES)

        save_raw(response=response, path=FX_DIR / f"fx_{start}_{end}.json")
        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        skipped , written = write_rates_csv(rows=rows, path=FX_RATE_FILE)
        parquet_written = write_rates_parquet(rows=rows, path=FX_RATE_PARQUET_FILE)
        logger.info("Wrote %d rows to %s", parquet_written, FX_RATE_PARQUET_FILE)

        logger.info("Rows written: %d", written)
        if skipped > 0:
            logger.warning("rows skipped: %d", skipped)
        logger.info("duration_ms= %.0f", (time.perf_counter() - started) * 1000)
    except FxApiError as e:
        logger.exception("extract_fx failed (retryable=%s)", e.retryable)
        raise SystemExit(1)
    except Exception:
        logger.exception("extract_fx failed")
        raise SystemExit(1)


if __name__ == "__main__":
    main()