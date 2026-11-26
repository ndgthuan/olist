-- Q: Total paid vs total item value, without the fan-out from 15.
-- Grain: one row per order on EACH side before the join (1-to-1 join, no fan-out)
-- Expected: 1 row. orders 99,440; paid 16,008,872.12 (= true total); items_total 15,843,409.78 (NULL for the 775)
-- Fix: aggregate each "many" table to one row per order FIRST, then join.
-- LEFT JOIN from payments: 775 orders have payments but no items (mostly unavailable /
--   canceled). An inner join drops them and loses 162,591.95 (15,846,280.17).
WITH items AS (
    SELECT
        order_id,
        count(*) AS n_items,
        sum(price + freight_value) AS items_total
    FROM raw.order_items
    GROUP BY order_id
),

payments AS (
    SELECT
        order_id,
        sum(payment_value) AS paid
    FROM raw.order_payments
    GROUP BY order_id
)

SELECT
    count(*) AS orders,
    round(sum(p.paid), 2) AS paid,
    round(sum(i.items_total), 2) AS items_total
FROM payments p
LEFT JOIN items i ON i.order_id = p.order_id;
