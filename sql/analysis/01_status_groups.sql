-- Q: How many orders are in each status group?
-- Grain: one row per status group
-- Expected rows: 3
WITH bucketed AS (
    SELECT 
	    order_id,
	    CASE
	        WHEN order_status = 'delivered' THEN 'done'
	        WHEN order_status IN ('canceled', 'unavailable') THEN 'failed'
	        ELSE 'in progress'
	    END AS status_group
    FROM raw.orders
)

SELECT 
    status_group, count(*) AS orders
FROM bucketed
GROUP BY status_group
ORDER BY orders DESC;