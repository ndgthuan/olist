-- Q: Q7 again, but with one review per order (latest, from 08).
-- Grain: one row per delivery group; each order counted once
-- Expected rows: 2 (on time 89,443 orders / 4.29; late 6,381 orders / 2.27)
-- Fix: Q7 joined every review, so orders with 2+ reviews counted twice
-- (reviews > orders). Now reviews = orders.
-- Result: averages did NOT change. Only ~550 duplicates, not biased up or down.
-- Still fixed, so the grain is honest: "late ORDERS average 2.27".
WITH ranked AS (
    SELECT
        *,
        ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY review_answer_timestamp DESC) AS rn
    FROM raw.order_reviews
),

delivered AS (
    SELECT
        o.order_id,
        o.order_delivered_customer_date::date > o.order_estimated_delivery_date::date AS is_late
    FROM raw.orders o
    WHERE o.order_status = 'delivered'
      AND o.order_delivered_customer_date IS NOT NULL
)

SELECT
    CASE WHEN d.is_late THEN 'late' ELSE 'on time' END AS delivery_group,
    count(*) AS reviews,
    count(DISTINCT d.order_id) AS orders,
    round(avg(r.review_score), 2) AS avg_rating
FROM delivered d
JOIN ranked r ON r.order_id = d.order_id AND r.rn = 1
GROUP BY delivery_group
ORDER BY avg_rating DESC;
