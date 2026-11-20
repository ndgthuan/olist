-- Q: What is the 3-month rolling average of orders (smooths out spikes)?
-- Grain: one row per month, Jan 2017 - Aug 2018 (trusted range, see 05)
-- Expected rows: 20 (Jan 2017 800; Mar 2017 1,754; Nov 2017 7,544 orders -> rolling 5,487)
-- Frame: ROWS BETWEEN 2 PRECEDING AND CURRENT ROW = this month + 2 before.
-- Nov 2017 (Black Friday) is pulled down by the normal Sep + Oct before it.
-- First 2 rows only have 1 and 2 months in their frame, so they aren't a true
-- 3-month average. Show them as NULL or drop them if that matters.
-- Assumes no missing months in this range (true here); otherwise use the calendar from 13.
WITH monthly AS (
    SELECT
        date_trunc('month', order_purchase_timestamp)::date AS month,
        count(*) AS orders
    FROM raw.orders
    WHERE order_purchase_timestamp >= '2017-01-01'
      AND order_purchase_timestamp < '2018-09-01'
    GROUP BY month
)

SELECT
    month,
    orders,
    round(avg(orders) OVER (ORDER BY month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 0) AS rolling_3m
FROM monthly
ORDER BY month;
