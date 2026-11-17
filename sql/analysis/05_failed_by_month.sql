-- Q: How many orders failed (canceled or unavailable) each purchase month?
-- Grain: one row per purchase month that has orders
-- Expected rows: 25 (Sep 2016 - Oct 2018; Nov 2016 has no orders, so no row)
-- Edge months are incomplete (dataset start/export cut): Sep-Dec 2016 and Sep-Oct 2018
-- have tiny counts, so their failed_pct (e.g. 100% in Oct 2018) is noise. Trust Jan 2017 - Aug 2018.
SELECT
    date_trunc('month', order_purchase_timestamp)::date AS month,
    count(*) AS orders,
    sum(CASE WHEN order_status IN ('canceled', 'unavailable') THEN 1 ELSE 0 END) AS failed,
    round(100.0 * sum(CASE WHEN order_status IN ('canceled', 'unavailable') THEN 1 ELSE 0 END)
      / count(*), 1) AS failed_pct
FROM raw.orders
GROUP BY month
ORDER BY month;