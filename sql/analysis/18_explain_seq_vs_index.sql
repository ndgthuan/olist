-- Q: How does Postgres find rows? Seq Scan vs Index Scan.
-- Grain: query plans (EXPLAIN ANALYZE runs the query and shows HOW it ran)
-- Expected: both queries return 1 row.
--   order_id    -> Index Scan using orders_pkey, ~0.08 ms, 4 buffers
--   customer_id -> Seq Scan, ~7-26 ms, reads all 1,840 pages, Rows Removed by Filter: 99,440
-- A PRIMARY KEY creates an index automatically; customer_id is a plain column.
-- Compare plans and Rows Removed, not exact ms (timing depends on what's cached).
EXPLAIN ANALYZE
SELECT * FROM raw.orders WHERE order_id = 'e481f51cbdc54678b7cc49136f2d6af7';

EXPLAIN ANALYZE
SELECT * FROM raw.orders WHERE customer_id = '9ef432eb6251297304e76186b10a928d';
