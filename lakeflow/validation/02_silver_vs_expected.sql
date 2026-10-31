-- Silver against the generator's ground truth (_expected/), for the clean dataset only.
-- Every count must be 0: silver holds exactly the expected latest version of every record.
-- Expected values are cast to the silver types, so the comparison does not depend on the session
-- time zone or on how decimals are printed.
USE CATALOG workspace;

WITH
e_customers AS (
  SELECT customer_id, name, email, region, CAST(created_at AS TIMESTAMP) AS created_at,
         CAST(updated_at AS TIMESTAMP) AS updated_at, CAST(source_updated_at AS TIMESTAMP) AS source_updated_at, event_id
  FROM read_files('/Volumes/workspace/retail_landing/raw/retail/_expected/customers.csv', format => 'csv', header => true,
       schema => 'customer_id STRING, name STRING, email STRING, region STRING, created_at STRING, updated_at STRING, source_updated_at STRING, event_id STRING')),
s_customers AS (
  SELECT customer_id, name, email, region, created_at, updated_at, source_updated_at, event_id FROM retail_silver.customers),
e_products AS (
  SELECT product_id, product_name, category, CAST(price AS DECIMAL(18,2)) AS price, status,
         CAST(source_updated_at AS TIMESTAMP) AS source_updated_at, event_id
  FROM read_files('/Volumes/workspace/retail_landing/raw/retail/_expected/products.csv', format => 'csv', header => true,
       schema => 'product_id STRING, product_name STRING, category STRING, price STRING, status STRING, source_updated_at STRING, event_id STRING')),
s_products AS (
  SELECT product_id, product_name, category, price, status, source_updated_at, event_id FROM retail_silver.products),
e_orders AS (
  SELECT order_id, customer_id, CAST(order_date AS TIMESTAMP) AS order_date, status,
         CAST(source_updated_at AS TIMESTAMP) AS source_updated_at, event_id
  FROM read_files('/Volumes/workspace/retail_landing/raw/retail/_expected/orders.csv', format => 'csv', header => true,
       schema => 'order_id STRING, customer_id STRING, order_date STRING, status STRING, source_updated_at STRING, event_id STRING')),
s_orders AS (
  SELECT order_id, customer_id, order_date, status, source_updated_at, event_id FROM retail_silver.orders),
e_order_items AS (
  SELECT order_item_id, order_id, product_id, CAST(quantity AS INT) AS quantity, CAST(unit_price AS DECIMAL(18,2)) AS unit_price,
         CAST(source_updated_at AS TIMESTAMP) AS source_updated_at, event_id
  FROM read_files('/Volumes/workspace/retail_landing/raw/retail/_expected/order_items.csv', format => 'csv', header => true,
       schema => 'order_item_id STRING, order_id STRING, product_id STRING, quantity STRING, unit_price STRING, source_updated_at STRING, event_id STRING')),
s_order_items AS (
  SELECT order_item_id, order_id, product_id, quantity, unit_price, source_updated_at, event_id FROM retail_silver.order_items),
e_payments AS (
  SELECT payment_id, order_id, payment_type, CAST(amount AS DECIMAL(18,2)) AS amount, method, status,
         CAST(payment_at AS TIMESTAMP) AS payment_at, CAST(source_updated_at AS TIMESTAMP) AS source_updated_at, event_id
  FROM read_files('/Volumes/workspace/retail_landing/raw/retail/_expected/payments.csv', format => 'csv', header => true,
       schema => 'payment_id STRING, order_id STRING, payment_type STRING, amount STRING, method STRING, status STRING, payment_at STRING, source_updated_at STRING, event_id STRING')),
s_payments AS (
  SELECT payment_id, order_id, payment_type, amount, method, status, payment_at, source_updated_at, event_id FROM retail_silver.payments)

SELECT 'customers' AS entity,
       (SELECT COUNT(*) FROM e_customers) AS expected_rows,
       (SELECT COUNT(*) FROM (SELECT * FROM e_customers EXCEPT ALL SELECT * FROM s_customers)) AS missing_from_silver,
       (SELECT COUNT(*) FROM (SELECT * FROM s_customers EXCEPT ALL SELECT * FROM e_customers)) AS unexpected_in_silver
UNION ALL
SELECT 'products', (SELECT COUNT(*) FROM e_products),
       (SELECT COUNT(*) FROM (SELECT * FROM e_products EXCEPT ALL SELECT * FROM s_products)),
       (SELECT COUNT(*) FROM (SELECT * FROM s_products EXCEPT ALL SELECT * FROM e_products))
UNION ALL
SELECT 'orders', (SELECT COUNT(*) FROM e_orders),
       (SELECT COUNT(*) FROM (SELECT * FROM e_orders EXCEPT ALL SELECT * FROM s_orders)),
       (SELECT COUNT(*) FROM (SELECT * FROM s_orders EXCEPT ALL SELECT * FROM e_orders))
UNION ALL
SELECT 'order_items', (SELECT COUNT(*) FROM e_order_items),
       (SELECT COUNT(*) FROM (SELECT * FROM e_order_items EXCEPT ALL SELECT * FROM s_order_items)),
       (SELECT COUNT(*) FROM (SELECT * FROM s_order_items EXCEPT ALL SELECT * FROM e_order_items))
UNION ALL
SELECT 'payments', (SELECT COUNT(*) FROM e_payments),
       (SELECT COUNT(*) FROM (SELECT * FROM e_payments EXCEPT ALL SELECT * FROM s_payments)),
       (SELECT COUNT(*) FROM (SELECT * FROM s_payments EXCEPT ALL SELECT * FROM e_payments))
ORDER BY entity;
