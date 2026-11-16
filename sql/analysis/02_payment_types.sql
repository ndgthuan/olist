-- Q: How many payments and how much money per payment type?
-- Grain: one row per payment_type
-- Expected rows: 5
SELECT
	payment_type,
	COUNT(*) AS payments,
	SUM(payment_value) AS total_value,
	ROUND(AVG(payment_value), 2) As avg_value
FROM raw.order_payments
GROUP BY payment_type
ORDER BY total_value DESC;