-- Q: Keep only the latest review for each order (dedup).
-- Grain: one row per order (that has a review)
-- Expected rows: 98,673 (= distinct orders in order_reviews; 551 older reviews dropped)
-- PARTITION BY = who competes (reviews of the same order);
-- ORDER BY = who wins (latest answer).
-- Tie-breaker: review_answer_timestamp has 0 ties inside an order;
-- review_creation_date has 157. With ties, ROW_NUMBER picks one at random,
-- so the "kept" review could change between runs.
WITH ranked AS (
    SELECT
        *,
        ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY review_answer_timestamp DESC) AS rn
    FROM raw.order_reviews
)

SELECT count(*) AS reviews_kept, count(DISTINCT order_id) AS orders
FROM ranked
WHERE rn = 1;
