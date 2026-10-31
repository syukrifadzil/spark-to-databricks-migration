-- Row counts per layer and a content fingerprint of each silver table.
-- Run in the SQL editor after every pipeline update. The fingerprint covers business and feed
-- columns only (not _ingested_at), so it must be unchanged by a rerun or a full refresh.
USE CATALOG workspace;

SELECT 'customers' AS entity,
       (SELECT COUNT(*) FROM retail_bronze.customers) AS bronze_rows,
       (SELECT COUNT(*) FROM retail_silver.customers) AS silver_rows,
       (SELECT COUNT(*) FROM retail_silver.customers_quarantine) AS quarantine_rows,
       (SELECT SUM(hash(customer_id, name, email, region, created_at, updated_at, source_updated_at, event_id))
          FROM retail_silver.customers) AS silver_fingerprint
UNION ALL
SELECT 'products',
       (SELECT COUNT(*) FROM retail_bronze.products),
       (SELECT COUNT(*) FROM retail_silver.products),
       (SELECT COUNT(*) FROM retail_silver.products_quarantine),
       (SELECT SUM(hash(product_id, product_name, category, price, status, source_updated_at, event_id))
          FROM retail_silver.products)
UNION ALL
SELECT 'orders',
       (SELECT COUNT(*) FROM retail_bronze.orders),
       (SELECT COUNT(*) FROM retail_silver.orders),
       (SELECT COUNT(*) FROM retail_silver.orders_quarantine),
       (SELECT SUM(hash(order_id, customer_id, order_date, status, source_updated_at, event_id))
          FROM retail_silver.orders)
UNION ALL
SELECT 'order_items',
       (SELECT COUNT(*) FROM retail_bronze.order_items),
       (SELECT COUNT(*) FROM retail_silver.order_items),
       (SELECT COUNT(*) FROM retail_silver.order_items_quarantine),
       (SELECT SUM(hash(order_item_id, order_id, product_id, quantity, unit_price, source_updated_at, event_id))
          FROM retail_silver.order_items)
UNION ALL
SELECT 'payments',
       (SELECT COUNT(*) FROM retail_bronze.payments),
       (SELECT COUNT(*) FROM retail_silver.payments),
       (SELECT COUNT(*) FROM retail_silver.payments_quarantine),
       (SELECT SUM(hash(payment_id, order_id, payment_type, amount, method, status, payment_at, source_updated_at, event_id))
          FROM retail_silver.payments)
ORDER BY entity;
