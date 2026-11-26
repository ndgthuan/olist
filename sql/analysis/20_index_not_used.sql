-- Q: When does Postgres ignore an index that exists?
-- Grain: query plans
-- Expected:
--   'delivered' (96,478 rows = 97%) -> Seq Scan, ~10-12 ms
--   'canceled'  (625 rows)          -> Index Scan using idx_orders_status, ~0.5 ms
-- The planner skips the index when most of the table matches: jumping row by row
-- through the index costs more than reading every page once. Forcing the index
-- (SET enable_seqscan = off) for 'delivered' gave 12.9 ms vs 12.4 ms: no gain.
-- The 'delivered' time is mostly RETURNING 96k rows; no index can make that smaller.
-- Indexes help selective filters (few rows), not filters that match most of the table.
CREATE INDEX IF NOT EXISTS idx_orders_status ON raw.orders (order_status);

EXPLAIN ANALYZE
SELECT * FROM raw.orders WHERE order_status = 'delivered';

EXPLAIN ANALYZE
SELECT * FROM raw.orders WHERE order_status = 'canceled';
