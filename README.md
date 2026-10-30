# olist

A batch data pipeline built on the [Olist Brazilian e-commerce dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce).
It extracts CSVs and daily FX rates, loads them into PostgreSQL, models them with dbt and runs on a schedule.

> Status: Week 2 done. Orders are cleaned (`clean_orders`), BRL→USD/VND rates are extracted (`extract_fx`), and orders are joined with their items, payments and FX rates and reconciled against the raw files (`build_orders`). Postgres, dbt and scheduling come next.

## How to set up

Requires Python 3.12+ and Git. Commands are for Windows PowerShell.

1. **Clone the repo**
   ```powershell
   git clone https://github.com/ndgthuan/olist.git
   cd olist
   ```
2. **Create and activate a virtual environment**
   ```powershell
   py -3.13 -m venv .venv
   .venv\Scripts\Activate.ps1
   ```
3. **Install the project with dev tools** (editable, so code changes apply without reinstalling)
   ```powershell
   python -m pip install -e ".[dev]"
   ```
4. **Download the data.** Get the dataset from Kaggle (free account) and unzip the 9 CSVs into `data/raw/olist/`.
   The `data/` folder is git-ignored.
5. **Copy the env file**
   ```powershell
   Copy-Item .env.example .env
   ```
6. **Run the tests.** They use no network and no real data files.
   ```powershell
   python -m pytest
   ```

If you move or rename the project folder, run step 3 again: the editable install remembers the old path.

## How to run

Run the steps in this order. `extract_fx` reads the date range from the clean orders file, so `clean_orders` must run first. `build_orders` needs the output of both.

```powershell
python -m pipeline.clean_orders
python -m pipeline.extract_fx
python -m pipeline.build_orders
```

| Step | Reads | Writes | Log |
|---|---|---|---|
| `clean_orders` | `data/raw/olist/olist_orders_dataset.csv` | `data/processed/orders_clean.csv`, `data/rejects/orders_rejects.csv` | `logs/clean_orders.log` |
| `extract_fx` | `data/processed/orders_clean.csv`, Frankfurter API | `data/raw/fx/fx_<start>_<end>.json`, `data/processed/fx_rates.csv`, `data/processed/fx_rates.parquet` | `logs/extract_fx.log` |
| `build_orders` | `data/processed/orders_clean.csv`, `data/processed/fx_rates.parquet`, `data/raw/olist/olist_order_items_dataset.csv`, `data/raw/olist/olist_order_payments_dataset.csv` | nothing yet: it builds and checks the joined table in memory | `logs/build_orders.log` |

Each step ends with exit code 1 if it fails, so a scheduler can see the failure. The details are in the log file.

## Project layout

```text
src/pipeline/   pipeline code, one module per step (clean_orders.py, extract_fx.py, build_orders.py)
tests/          pytest tests and tiny fixture files
data/raw/       source data exactly as received: Olist CSVs and FX API responses (not in git)
data/processed/ cleaned output (not in git)
logs/           one log file per step (not in git)
```

## The data: what one row means

Checked by counting duplicate keys in each file.

| Table | One row is... | Unique key |
|---|---|---|
| `orders` | one order (99,441 rows) | `order_id` |
| `order_items` | one item line inside an order. An order with 3 items has 3 rows | `order_id` + `order_item_id` |
| `order_payments` | one payment for an order. An order paid with a voucher and a card has 2 rows | `order_id` + `payment_sequential` |
| `order_reviews` | one review of one order. A few `review_id`s cover several orders | `review_id` + `order_id` |
| `customers` | one customer *per order*. The same person gets a new `customer_id` each order; `customer_unique_id` is the real person | `customer_id` |
| `sellers` | one seller | `seller_id` |
| `products` | one product | `product_id` |
| `geolocation` | one lat/lng point. A zip prefix has many points, so dedupe before joining | none |
| `product_category_name_translation` | one Portuguese category and its English name | `product_category_name` |

Joining `orders` to `order_items` gives one row per item, not per order. Sum item prices before comparing with order-level totals.

## Cleaning rules: olist_orders

Rules for `olist_orders_dataset.csv` (99,441 rows), decided after profiling the file. The counts are from the downloaded dataset.

Principle: reject data that is broken, not data that is bad news. A late delivery is a real fact about the business and stays in.

### Converted

| Column | Rule | Why |
|---|---|---|
| All 5 timestamp columns | Parse `YYYY-MM-DD HH:MM:SS`, label as `America/Sao_Paulo`, convert to UTC | The source has no time zone. Olist is a Brazilian company, so the values are São Paulo local time. A zone name is used, not a fixed `-03:00`, because Brazil had summer time in 2016–2018 |
| `order_status` | Trim spaces, lowercase | So the same status is always written the same way |

### Kept, with a warning in the log

These rows look odd but are not provably wrong, so the order stays and the run logs how many there are.

| Case | Today | Decision | Why |
|---|---|---|---|
| `delivered` with no `order_delivered_customer_date` | 8 | Keep, date stays empty | The order and its revenue are real. Delivery-time metrics skip rows with no delivery date |
| `delivered` with no `order_approved_at` | 14 | Keep, date stays empty | Same reason, and the approval time is not used for the main metrics |
| `canceled` that has a delivery date | 6 | Keep | It can be a real case (delivered, then canceled and refunded) and cannot be checked from this file |
| Carrier pickup before purchase | 166 | Keep | The pickup time likely comes from another system's clock and is not used for the main metrics |

An empty timestamp is normal for orders that have not reached that step yet (for example `shipped` has no delivery date). Empty stays empty; it is never replaced with a made-up date.

### Rejected

A rejected row is not written to the clean file. It goes to the reject file with the reason.

| Case | Today |
|---|---|
| Empty `order_id` or `customer_id` | 0 |
| Empty `order_purchase_timestamp` or `order_estimated_delivery_date` | 0 |
| A timestamp that cannot be parsed | 0 |
| `order_status` is not one of the 8 known values: `created`, `approved`, `invoiced`, `processing`, `shipped`, `delivered`, `canceled`, `unavailable` | 0 |
| Delivered to the customer before the purchase time | 0 |
| Duplicate `order_id`: the first row is kept, later ones are rejected | 0 |

Known limit of the duplicate rule: the first row in the file is not always the correct one. A later version may keep the most recent row instead.

Reject file columns: `line` (line number in the source CSV), `order_id`, `reason`.

### Checks on every run

- rows read = rows kept + rows rejected
- `order_id` is unique in the clean file
- the clean file is not empty

## Cleaning rules: FX rates

Daily exchange rates from [Frankfurter v2](https://frankfurter.dev/) (`/v2/rates`), used to convert order payments from BRL to USD and VND. One API call returns the whole range, so there is no pagination.

### Date range

The range is taken from the data, not hard-coded: the earliest and latest `order_purchase_timestamp` in `orders_clean.csv`, **plus one day on each side**.

Why the extra days: the clean file is in UTC, but an order's business date is its São Paulo date. The first order was placed on 4 Sep 2016 at 21:15 in São Paulo, which is 5 Sep 00:15 UTC. Without the padding, its rate would be missing. Current range: `2016-09-04` to `2018-10-18`.

### Request and retries

| Failure | Retried? | Why |
|---|---|---|
| Timeout, connection error | Yes | The network often recovers within seconds |
| HTTP 408, 425, 429, 5xx | Yes | The server is busy or failing; the same request may work later |
| Other HTTP 4xx (for example 422 for an unknown currency) | No | The request itself is wrong; asking again gives the same answer |

Up to 3 attempts, waiting 1 s then 2 s between them. Retrying is safe because the request is a GET: it only reads.

### Rejected: the run fails

The response is checked before anything is saved, so a broken response never replaces a good raw file.

| Case |
|---|
| The response is not a list |
| The response is empty |
| A row has no `date` or no `quote` |
| A row has a currency that was not requested |

### Skipped, with a warning in the log

| Case | Today |
|---|---|
| `rate` is missing or not a number | 0 |

### Kept, with a warning in the log

| Case | Today | Decision |
|---|---|---|
| A date where one currency has a rate and the other does not | 1: VND has no rate for 2017-07-15 (USD does). 98 orders have that São Paulo business date (119 by UTC date) | Keep the rows that exist. The gap is filled when rates are joined to orders (below) |

### Rule for the join with orders

When an order's date has no rate for a currency, use the **latest earlier rate**, at most 3 days back. This is how banks and accounting treat days without a published rate, and FX moves little from one day to the next. The date the rate really comes from is kept in a `rate_date` column, so a filled rate is never presented as that day's rate. If the gap is longer than 3 days, the converted value stays empty and the run logs a warning. Leaving all gaps empty was rejected because sums would silently skip those orders and under-report revenue.

### Files

- Raw: the API response is saved byte for byte to `data/raw/fx/fx_<start>_<end>.json`.
- Processed: `data/processed/fx_rates.csv` with columns `date`, `quote`, `rate` (one row per date and currency).
- Processed: `data/processed/fx_rates.parquet` with the same rows and an explicit schema: `date` as `date32`, `quote` as `string`, `rate` as `float64`, none of them nullable. Unlike the CSV, the types are stored in the file, so a reader gets real dates without parsing. Rows with a non-numeric rate are skipped in both files, so the two always match (1,549 rows today). A test checks the schema, the skipped row and that no `.tmp` file is left.
- All three are written to a `.tmp` file first and then renamed, so a crash never leaves a half-written file.

## Rules: build_orders

`build_orders` joins every clean order with its items, its payments and its FX rates, then checks that no money was lost or counted twice.

### Grain: one row per order

`order_items` has one row per item and `order_payments` one row per payment, so joining them both to orders directly would repeat each payment once per item. On this data that inflates the payment total by 28% (20,470,726.66 instead of 16,008,872.12). So both are first summed per order:

| Summary | Columns |
|---|---|
| items per order | `item_count`, `item_price` (sum of `price`), `item_freight` (sum of `freight_value`) |
| payments per order | `payment_count`, `payment_total` (sum of `payment_value`) |

Both summaries are then left-joined to orders with `validate="one_to_one"`, so a duplicate `order_id` on either side stops the run. The joined table has exactly as many rows as orders (99,441), which is asserted. Each join adds an indicator column (`_items_match`, `_payments_match`) to find orders without a match.

### Kept, with a warning in the log

| Case | Today | Why it is kept |
|---|---|---|
| Order with no items | 775: `unavailable` 603, `canceled` 164, `created` 5, `invoiced` 2, `shipped` 1 | Mostly orders that never got a product. The one `shipped` order without items is odd and cannot be checked from these files |
| Order with no payment | 1 (`delivered`, items 134.97 + freight 8.49) | The order is real; its payment row is missing from the source |

Their item or payment columns stay empty, never 0, so they are not mistaken for free orders.

### Business date and FX rates

- `order_date` is the purchase date **in São Paulo** (the clean file is in UTC). The first order is 4 Sep 2016 21:15 São Paulo time, which is already 5 Sep in UTC.
- Rates are joined with `pd.merge_asof`, one currency at a time: the rate of the order date, or else the latest earlier rate at most 3 days back (the rule above). The columns `rate_usd`, `rate_date_usd`, `rate_vnd`, `rate_date_vnd` show the rate and the day it really comes from.
- Today: every order has both rates. USD uses the order's own day for all orders. VND uses 2017-07-14's rate for the 98 orders of 2017-07-15.

### Reconcile against the raw files

The run fails if any of these does not hold (money within 0.01, because of float rounding):

| Check | Source | Joined table |
|---|---|---|
| item rows | 112,650 rows in `order_items` | sum of `item_count` |
| item money | 15,843,553.24 (price + freight) | sum of `item_price` + `item_freight` |
| payment rows | 103,886 rows in `order_payments` | sum of `payment_count` |
| payment money | 16,008,872.12 | sum of `payment_total` |

Items and payments are both correct but do not measure the same thing: customers paid 165,318.88 (about 1%) more than items plus freight. The gap is explained to the cent:

| Part | Amount |
|---|---|
| Paid on the 775 orders with no items (probably refunded later; refunds are not in the dataset) | +162,591.95 |
| Orders with both, where payment ≠ items + freight: 291 paid more (likely installment interest), 90 paid less (likely discounts) | +2,870.39 |
| Items of the one order with no payment | −143.46 |
| **Total** | **165,318.88** |

So revenue from payments and revenue from items are different numbers. Any report must say which one it uses.
