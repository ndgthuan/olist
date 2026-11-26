-- Q: What goes wrong when you join two "many" tables (items + payments) on order_id?
-- Grain: BROKEN. One row per (item x payment) pair, not per order or per payment.
-- Expected: order 03ecec24… has 2 items x 2 payments = 4 rows; sum = 751.46,
--   but the customer really paid 375.73 (319.34 + 56.39). Each payment counted twice.
-- Whole table: sum(payment_value) after the join = 20,308,134.71 (117,601 rows)
--   vs the true 16,008,872.12 from order_payments alone (+27%). No error is raised.
-- Fix in 16: aggregate each side to one row per order BEFORE joining.
SELECT
    i.order_item_id,
    i.price,
    p.payment_sequential,
    p.payment_value
FROM raw.order_items i
JOIN raw.order_payments p ON p.order_id = i.order_id
WHERE i.order_id = '03ecec245220b63fd7f68c1737ba99ba'
ORDER BY i.order_item_id, p.payment_sequential;

SELECT round(sum(p.payment_value), 2) AS fanout_total
FROM raw.order_items i
JOIN raw.order_payments p ON p.order_id = i.order_id;
