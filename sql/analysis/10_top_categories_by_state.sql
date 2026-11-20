-- Q: What are the top 3 product categories in each of the 3 biggest states?
-- Grain: one row per (state, category) with rank <= 3
-- Expected rows: 9 (SP, RJ, MG x 3). All 3 states: #1 bed_bath_table, #2 health_beauty.
--   SP bed_bath_table 4,416 orders.
-- Top N per group: LIMIT can't do it (it limits the whole result),
-- so RANK() OVER (PARTITION BY state). RANK keeps ties, so a state could show 4+ rows.
-- count(DISTINCT order_id): joining order_items fans out (1 order, 3 items = 3 rows).
-- LEFT JOIN translation: an inner join would silently drop the 610 products with
-- no category. Their orders show as category NULL.
WITH top_states AS (
    SELECT c.customer_state
    FROM raw.orders o
    JOIN raw.customers c ON c.customer_id = o.customer_id
    GROUP BY c.customer_state
    ORDER BY count(*) DESC
    LIMIT 3
),

category_orders AS (
    SELECT
        c.customer_state,
        t.product_category_name_english AS category,
        count(DISTINCT o.order_id) AS orders
    FROM raw.orders o
    JOIN raw.customers c ON c.customer_id = o.customer_id
    JOIN raw.order_items i ON i.order_id = o.order_id
    JOIN raw.products p ON p.product_id = i.product_id
    LEFT JOIN raw.product_category_name_translation t
        ON t.product_category_name = p.product_category_name
    WHERE c.customer_state IN (SELECT customer_state FROM top_states)
    GROUP BY c.customer_state, t.product_category_name_english
),

ranked AS (
    SELECT
        *,
        RANK() OVER (PARTITION BY customer_state ORDER BY orders DESC) AS rnk
    FROM category_orders
)

SELECT *
FROM ranked
WHERE rnk <= 3
ORDER BY customer_state, rnk;
