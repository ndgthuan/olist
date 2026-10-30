from pathlib import Path
import logging
import time
import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
FX_RATE_PARQUET_FILE = PROCESSED_DIR / "fx_rates.parquet"
OLIST_DIR = RAW_DIR / "olist"
LOG_DIR = PROJECT_DIR / "logs"
ORDER_ITEM_FILE = OLIST_DIR / "olist_order_items_dataset.csv"
PAYMENT_FILE = OLIST_DIR / "olist_order_payments_dataset.csv"
LOG_FILE = LOG_DIR / "build_orders.log"
ORDER_CLEAN_FILE = PROCESSED_DIR / "orders_clean.csv"
ORDER_DATE_COLUMNS = ["order_purchase_timestamp", "order_approved_at",
                      "order_delivered_carrier_date", "order_delivered_customer_date", "order_estimated_delivery_date"]
logger = logging.getLogger(__name__)


def load_orders(path: Path) -> pd.DataFrame:
    orders = pd.read_csv(path, parse_dates=ORDER_DATE_COLUMNS)
    return orders


def load_items(path: Path) -> pd.DataFrame:
    items = pd.read_csv(path, parse_dates=["shipping_limit_date"])
    return items


def load_payments(path: Path) -> pd.DataFrame:
    payments = pd.read_csv(path)
    return payments


def summarize_items(items: pd.DataFrame) -> pd.DataFrame:
    summary = items.groupby("order_id", as_index=False).agg(
        item_count=("order_item_id", "size"),
        item_price=("price", "sum"),
        item_freight=("freight_value", "sum"),
    )
    return summary


def summarize_payments(payments: pd.DataFrame) -> pd.DataFrame:
    summary = payments.groupby("order_id", as_index=False).agg(
        payment_count=("order_id", "size"),
        payment_total=("payment_value", "sum"),
    )
    return summary


def join_orders(orders, items_summary, payments_summary) -> pd.DataFrame:
    joined = orders.merge(
        items_summary, on="order_id", how="left",
        validate="one_to_one", indicator="_items_match",
    )
    joined = joined.merge(
        payments_summary, on="order_id", how="left",
        validate="one_to_one", indicator="_payments_match",
    )
    return joined


def load_fx_rates(path: Path):
    fx = pd.read_parquet(path=path)
    fx["date"] = pd.to_datetime(fx["date"]).astype("datetime64[us]")
    return fx


def add_fx_rate(orders: pd.DataFrame, fx: pd.DataFrame, quote: str) -> pd.DataFrame:
    rate_col = f"rate_{quote.lower()}"
    date_col = f"rate_date_{quote.lower()}"

    rates = fx[fx["quote"] == quote][["date", "rate"]]
    rates = rates.rename(columns={"date": date_col, "rate": rate_col})
    rates = rates.sort_values(date_col)

    return pd.merge_asof(
        orders.sort_values("order_date"),
        rates,
        left_on="order_date",
        right_on=date_col,
        direction="backward",
        tolerance=pd.Timedelta(days=3),
    )

def reconcile(joined: pd.DataFrame, items: pd.DataFrame, payments: pd.DataFrame):
    assert len(items) == joined["item_count"].sum(), (
    f"item rows: source {len(items)} vs joined {joined['item_count'].sum()}"
    )

    source_items = items["price"].sum() + items["freight_value"].sum()
    joined_items = joined["item_price"].sum() + joined["item_freight"].sum()

    assert abs(source_items - joined_items) < 0.01
    assert len(payments) == joined["payment_count"].sum()
    assert abs(payments["payment_value"].sum() - joined["payment_total"].sum()) < 0.01
    logger.info("Items total (price + freight): %.2f", joined_items)
    logger.info("Payments total: %.2f", joined["payment_total"].sum())



def main() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                        encoding="utf-8", level=logging.INFO, filename=LOG_FILE)
    try:
        started = time.perf_counter()
        orders = load_orders(ORDER_CLEAN_FILE)
        items = load_items(ORDER_ITEM_FILE)
        payments = load_payments(PAYMENT_FILE)
        items_summary = summarize_items(items=items)
        payments_summary = summarize_payments(payments=payments)
        joined = join_orders(
            orders=orders, items_summary=items_summary, payments_summary=payments_summary)
        joined["order_date"] = (
            joined["order_purchase_timestamp"]
            .dt.tz_convert("America/Sao_Paulo")
            .dt.tz_localize(None)
            .dt.normalize()
        )
        fx = load_fx_rates(FX_RATE_PARQUET_FILE)
        joined = add_fx_rate(joined, fx, "USD")
        joined = add_fx_rate(joined, fx, "VND")
        no_items = joined["_items_match"] == "left_only"
        no_payment = joined["_payments_match"] == "left_only"
        logger.warning("Orders with no items: %d", no_items.sum())
        logger.warning("Orders with no payment: %d", no_payment.sum())
        assert orders["order_id"].is_unique
        assert items_summary["order_id"].is_unique
        assert payments_summary["order_id"].is_unique
        assert len(joined) == len(orders)
        logger.info("Orders with items: %d", len(items_summary))
        logger.info("Orders with payments: %d", len(payments_summary))
        logger.info("Orders loaded: %d", len(orders))
        logger.info("Items loaded: %d", len(items))
        logger.info("Payments loaded: %d", len(payments))
        logger.info("No-item orders by status: %s",
                    joined.loc[no_items, "order_status"].value_counts().to_dict())
        for quote in ["USD", "VND"]:
            rate_col = f"rate_{quote.lower()}"
            date_col = f"rate_date_{quote.lower()}"
            missing = joined[rate_col].isna().sum()
            filled = (joined[date_col].notna() & (
                joined[date_col] != joined["order_date"])).sum()
            if missing > 0:
                logger.warning("%s: %d orders have no rate", quote, missing)
            logger.info("%s: %d orders use an earlier day's rate",
                        quote, filled)
        reconcile(joined=joined, items=items, payments=payments)
        logger.info("duration_ms= %.0f",
                    (time.perf_counter() - started) * 1000)
    except Exception:
        logger.exception("build_orders failed")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
