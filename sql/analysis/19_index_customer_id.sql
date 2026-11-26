-- Q: Does an index on customer_id fix the Seq Scan from 18?
-- Grain: query plan
-- Expected: Index Scan using idx_orders_customer_id, ~0.06 ms (was Seq Scan ~6.7 ms, ~120x).
-- Trade-off: every index is a sorted copy that must be updated on EVERY write,
-- so more indexes = faster reads but slower loads (load_raw COPYs 1.5M rows).
-- Index columns you filter/join on often; for big bulk loads: drop, load, recreate.
-- Not in sql/raw_schema.sql yet, so a fresh setup won't have it.
CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON raw.orders (customer_id);

EXPLAIN ANALYZE
SELECT * FROM raw.orders WHERE customer_id = '9ef432eb6251297304e76186b10a928d';
