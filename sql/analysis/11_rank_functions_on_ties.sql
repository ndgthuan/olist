-- Q: How do ROW_NUMBER, RANK and DENSE_RANK differ when there are ties?
-- Grain: one row per category in RR (Roraima), top 10 by orders
-- Expected rows: 10. Top 2 are tied on 6 orders (health_beauty, sports_leisure).
--   row_num   1, 2, 3, 4 ...  always unique; picks a tie winner at random
--   rnk       1, 1, 3, 4 ...  ties share a rank, then SKIPS (2 rows are ahead of #3)
--   dense_rnk 1, 1, 2, 3 ...  ties share a rank, no gaps
-- "Top 1" with ROW_NUMBER silently hides the tied category; RANK/DENSE_RANK show both.
-- RR because big states have no ties at the top.
WITH category_orders AS (
    SELECT
        t.product_category_name_english AS category,
        count(DISTINCT o.order_id) AS orders
    FROM raw.orders o
    JOIN raw.customers c ON c.customer_id = o.customer_id
    JOIN raw.order_items i ON i.order_id = o.order_id
    JOIN raw.products p ON p.product_id = i.product_id
    LEFT JOIN raw.product_category_name_translation t
        ON t.product_category_name = p.product_category_name
    WHERE c.customer_state = 'RR'
    GROUP BY t.product_category_name_english
)

SELECT
    category,
    orders,
    ROW_NUMBER() OVER (ORDER BY orders DESC) AS row_num,
    RANK() OVER (ORDER BY orders DESC) AS rnk,
    DENSE_RANK() OVER (ORDER BY orders DESC) AS dense_rnk
FROM category_orders
ORDER BY orders DESC
LIMIT 10;
