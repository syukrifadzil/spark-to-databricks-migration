-- Anomaly handling, after batch_004 to batch_013 of data/raw/anomalous have been ingested on top
-- of the clean dataset. Each row is one check; status is ok when observed equals expected.
-- Expected values come from data/raw/anomalous/_anomaly_manifest.json (seed 7, 5 rows per scenario).
USE CATALOG workspace;

WITH quarantine AS (
  SELECT rule FROM retail_silver.customers_quarantine LATERAL VIEW explode(_failed_rules) r AS rule
  UNION ALL SELECT rule FROM retail_silver.products_quarantine LATERAL VIEW explode(_failed_rules) r AS rule
  UNION ALL SELECT rule FROM retail_silver.orders_quarantine LATERAL VIEW explode(_failed_rules) r AS rule
  UNION ALL SELECT rule FROM retail_silver.order_items_quarantine LATERAL VIEW explode(_failed_rules) r AS rule
  UNION ALL SELECT rule FROM retail_silver.payments_quarantine LATERAL VIEW explode(_failed_rules) r AS rule
),
checks AS (
  -- Quarantine: one reason per bad row, nothing else rejected
  SELECT 'null_required: customers.customer_id.required' AS check_name,
         (SELECT COUNT(*) FROM quarantine WHERE rule = 'customers.customer_id.required') AS observed, 5 AS expected
  UNION ALL SELECT 'null_required: orders.status.required',
         (SELECT COUNT(*) FROM quarantine WHERE rule = 'orders.status.required'), 5
  UNION ALL SELECT 'null_required: payments.order_id.required',
         (SELECT COUNT(*) FROM quarantine WHERE rule = 'payments.order_id.required'), 5
  UNION ALL SELECT 'negative_amount: payments.amount.range',
         (SELECT COUNT(*) FROM quarantine WHERE rule = 'payments.amount.range'), 5
  UNION ALL SELECT 'malformed_timestamp: orders.order_date.type',
         (SELECT COUNT(*) FROM quarantine WHERE rule = 'orders.order_date.type'), 5
  UNION ALL SELECT 'malformed_type: order_items.quantity.type',
         (SELECT COUNT(*) FROM quarantine WHERE rule = 'order_items.quantity.type'), 5
  UNION ALL SELECT 'malformed_type: payments.amount.type',
         (SELECT COUNT(*) FROM quarantine WHERE rule = 'payments.amount.type'), 5
  UNION ALL SELECT 'all quarantine reasons', (SELECT COUNT(*) FROM quarantine), 35
  -- Sequencing: the conflicting copy with the higher event_id wins; late versions lose
  UNION ALL SELECT 'duplicate_key_conflict: silver payments from EVT-A004',
         (SELECT COUNT(*) FROM retail_silver.payments WHERE event_id LIKE 'EVT-A004-%'), 5
  UNION ALL SELECT 'late_arrival: silver orders from EVT-A012',
         (SELECT COUNT(*) FROM retail_silver.orders WHERE event_id LIKE 'EVT-A012-%'), 0
  -- Quarantined updates leave the previous valid version in place
  UNION ALL SELECT 'null_required: silver orders with null status',
         (SELECT COUNT(*) FROM retail_silver.orders WHERE status IS NULL), 0
  UNION ALL SELECT 'malformed_timestamp: silver orders with null order_date',
         (SELECT COUNT(*) FROM retail_silver.orders WHERE order_date IS NULL), 0
  -- Orphans are kept, not rejected
  UNION ALL SELECT 'invalid_reference: orders for CUST-X99999',
         (SELECT COUNT(*) FROM retail_silver.orders WHERE customer_id = 'CUST-X99999'), 5
  UNION ALL SELECT 'invalid_reference: items for PROD-X9999',
         (SELECT COUNT(*) FROM retail_silver.order_items WHERE product_id = 'PROD-X9999'), 5
  UNION ALL SELECT 'invalid_reference: payments for ORD-X9999999',
         (SELECT COUNT(*) FROM retail_silver.payments WHERE order_id = 'ORD-X9999999'), 5
  UNION ALL SELECT 'payment_mismatch: extra charges in silver',
         (SELECT COUNT(*) FROM retail_silver.payments WHERE payment_id LIKE 'PAY-X008%'), 5
  -- Schema evolution: the extra column is kept in bronze, ignored by silver
  UNION ALL SELECT 'schema_evolution: bronze rows with rescued data',
         (SELECT COUNT(*) FROM retail_bronze.customers WHERE _rescued_data IS NOT NULL), 5
  UNION ALL SELECT 'schema_evolution: silver customers from EVT-A011',
         (SELECT COUNT(*) FROM retail_silver.customers WHERE event_id LIKE 'EVT-A011-%'), 5
)
SELECT check_name, observed, expected, IF(observed = expected, 'ok', 'FAIL') AS status FROM checks;
