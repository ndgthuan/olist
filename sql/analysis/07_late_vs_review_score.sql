-- Q: Do late deliveries get worse review scores?
-- Grain: one row per delivery group (late / on time)
-- Expected rows: 2 (on time 4.29 avg / late 2.27 avg)
-- Only delivered orders with a delivery date; late = later DAY than estimated (see 03).
-- Grain check: reviews > orders, because some orders have more than one review,
-- so the average is per review, not per order. Orders without a review drop out
-- of the inner join.
WITH delivered AS (
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
JOIN raw.order_reviews r ON r.order_id = d.order_id
GROUP BY delivery_group
ORDER BY avg_rating DESC;
