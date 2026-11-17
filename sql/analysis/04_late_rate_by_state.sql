-- Q: Which customer states have the worst late-delivery rate?
-- Grain: one row per customer_state
-- Expected rows: 5 (top 5 of the 12 states with >= 1,000 delivered orders)
-- Only delivered orders with a delivery date; late = later DAY than estimated (see 03).
-- States under 1,000 orders are left out: too small for a fair rate (AL would top at 21.4% on 397 orders).
WITH delivered AS (
    SELECT o.order_id,
           c.customer_state,
           order_delivered_customer_date::date > order_estimated_delivery_date::date AS is_late          -- use your ::date rule from 03!
    FROM raw.orders o
    JOIN raw.customers c ON c.customer_id = o.customer_id
    WHERE o.order_status = 'delivered'
      AND order_delivered_customer_date IS NOT NULL
),
by_state AS (
    SELECT customer_state,
           count(*) AS delivered,
           count(*) FILTER (WHERE is_late) AS late
    FROM delivered
    GROUP BY customer_state
)
SELECT customer_state, delivered, late,
       round(100.0 * late / delivered, 1) AS late_pct
FROM by_state
WHERE delivered >= 1000
ORDER BY late_pct DESC
LIMIT 5;