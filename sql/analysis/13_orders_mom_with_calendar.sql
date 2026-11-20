-- Q: Q12 again, but with every month present (no skipped months).
-- Grain: one row per calendar month, Sep 2016 - Oct 2018
-- Expected rows: 26 (Nov 2016 = 0 orders; Dec 2016 now compared to Nov -> pct NULL)
-- GROUP BY can't create months that have no rows, so build a calendar with
-- generate_series and LEFT JOIN the counts onto it; coalesce(…, 0) for empty months.
-- NULLIF(prev, 0): dividing by 0 would crash the whole query; NULL = "no % possible".
WITH monthly AS (
    SELECT
        date_trunc('month', order_purchase_timestamp)::date AS month,
        count(*) AS orders
    FROM raw.orders
    GROUP BY month
),

calendar AS (
    SELECT generate_series(min(month), max(month), interval '1 month')::date AS month
    FROM monthly
),

filled AS (
    SELECT
        c.month,
        coalesce(m.orders, 0) AS orders
    FROM calendar c
    LEFT JOIN monthly m ON m.month = c.month
)

SELECT
    month,
    orders,
    LAG(orders) OVER (ORDER BY month) AS prev_orders,
    round(100.0 * (orders - LAG(orders) OVER (ORDER BY month))
          / NULLIF(LAG(orders) OVER (ORDER BY month), 0), 1) AS pct_change
FROM filled
ORDER BY month;
