-- Q: For each order, does the amount paid match items price + freight?
-- Grain: one row per result group (orders that have both items and payments)
-- Expected rows: 3. match 98,362 / paid more 264 (+3,070.14) / paid less 39 (-199.08)
-- Data quality check (reconciliation). Tolerance 0.01: money split across payments
-- is rounded, so exact "= 0" would flag cent differences as errors.
-- "paid more" orders average 6.3 installments vs 2.9 for matches, 97% credit card:
-- likely installment interest. A finding to confirm with the business, not to "fix".
WITH items AS (
    SELECT
        order_id,
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
),

compared AS (
    SELECT
        p.order_id,
        p.paid - i.items_total AS diff
    FROM payments p
    JOIN items i ON i.order_id = p.order_id
)

SELECT
    CASE
        WHEN abs(diff) <= 0.01 THEN 'match'
        WHEN diff > 0 THEN 'paid more'
        ELSE 'paid less'
    END AS result,
    count(*) AS orders,
    round(sum(diff), 2) AS total_diff
FROM compared
GROUP BY result
ORDER BY orders DESC;
