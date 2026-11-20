-- Q: How do monthly orders change compared to the previous month?
-- Grain: one row per month that HAS orders
-- Expected rows: 25 (first row prev = NULL; Oct 2016 +8000.0%; Nov 2017 +62.9% Black Friday)
-- LAG = value from the previous ROW, not the previous month.
-- TRAP: Nov 2016 has no orders, so there's no row for it and Dec 2016 is compared to
-- Oct 2016 (-99.7%). Fixed in 13 with a generate_series calendar.
-- Brackets matter: 100.0 * orders - LAG / LAG = orders*100 - 1 (no error, wrong numbers).
-- Edge months are partial (see 05), so their % changes are noise.
WITH monthly AS (
    SELECT
        date_trunc('month', order_purchase_timestamp)::date AS month,
        count(*) AS orders
    FROM raw.orders
    GROUP BY month
)

SELECT
    month,
    orders,
    LAG(orders) OVER (ORDER BY month) AS prev_orders,
    orders - LAG(orders) OVER (ORDER BY month) AS diff,
    round(100.0 * (orders - LAG(orders) OVER (ORDER BY month))
          / LAG(orders) OVER (ORDER BY month), 1) AS pct_change
FROM monthly
ORDER BY month;
