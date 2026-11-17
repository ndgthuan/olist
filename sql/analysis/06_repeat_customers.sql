-- Q: How many real customers bought once, twice, or 3+ times?
-- Grain: one row per buyer type
-- Expected rows: 3 (93,099 / 2,745 / 252 = 96,096 people; repeat rate 3.1%)
-- customer_id is new for every order, so people are counted by customer_unique_id.
WITH orders_per_customer AS (
    SELECT c.customer_unique_id,
           count(*) AS orders
    FROM raw.orders o
    JOIN raw.customers c ON o.customer_id = c.customer_id 
    GROUP BY c.customer_unique_id
),
bucketed AS (
    SELECT 
    	CASE
        	WHEN orders = 1 THEN '1 order'
            WHEN orders = 2 THEN '2 orders'
            ELSE '3+ orders'
          END AS buyer_type
    FROM orders_per_customer
)
SELECT buyer_type, count(*) AS customers
FROM bucketed
GROUP BY buyer_type 
ORDER BY buyer_type;