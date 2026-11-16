-- Q: Of the delivered orders, how many arrived late vs on time?
-- Grain: one row per delivery group
-- Expected rows: 3 (on time 89,936 / late 6,534 / no delivery date 8; total 96,478 = delivered)
-- late = delivered on a later DAY than estimated. The estimate is always midnight
-- (a date, not a time), so comparing timestamps would wrongly call 1,292 orders
-- delivered on the promised day "late".
-- NULL check comes first: NULL > date is NULL, which would fall into ELSE as "on time".
WITH bucketed AS (
    SELECT
        order_id,
        CASE
            WHEN order_delivered_customer_date IS NULL THEN 'no delivery date'
            WHEN order_delivered_customer_date::date > order_estimated_delivery_date::date THEN 'late'
            ELSE 'on time'
        END AS delivery_group
    FROM raw.orders
    WHERE order_status = 'delivered'
)

SELECT
    delivery_group, count(*) AS orders
FROM bucketed
GROUP BY delivery_group
ORDER BY orders DESC;
