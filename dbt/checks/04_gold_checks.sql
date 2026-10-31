-- Gold checks after `dbt build`. Run in the SQL editor. Each row compares a mart total with the
-- same quantity computed directly from silver, so a join fan-out or a lost row in a mart shows up.
-- Not a dbt path: dbt does not run or build anything in this folder.
USE CATALOG workspace;

WITH
sold AS (SELECT * FROM retail_silver.orders WHERE status IN ('paid', 'shipped', 'delivered')),
succeeded AS (SELECT * FROM retail_silver.payments WHERE status = 'succeeded'),
checks AS (
  SELECT 'customer_lifetime_value rows = silver customers' AS check_name,
         (SELECT COUNT(*) FROM retail_gold.mart_customer_lifetime_value) AS observed,
         (SELECT COUNT(*) FROM retail_silver.customers) AS expected
  UNION ALL SELECT 'product_performance rows = silver products',
         (SELECT COUNT(*) FROM retail_gold.mart_product_performance),
         (SELECT COUNT(*) FROM retail_silver.products)
  UNION ALL SELECT 'daily orders_placed = silver orders',
         (SELECT SUM(orders_placed) FROM retail_gold.mart_daily_sales),
         (SELECT COUNT(*) FROM retail_silver.orders)
  UNION ALL SELECT 'daily orders_sold = silver sold orders',
         (SELECT SUM(orders_sold) FROM retail_gold.mart_daily_sales),
         (SELECT COUNT(*) FROM sold)
  UNION ALL SELECT 'lifetime orders_sold = sold orders of known customers',
         (SELECT SUM(orders_sold) FROM retail_gold.mart_customer_lifetime_value),
         (SELECT COUNT(*) FROM sold WHERE customer_id IN (SELECT customer_id FROM retail_silver.customers))
  UNION ALL SELECT 'daily gross_sales = silver sold line totals',
         (SELECT SUM(gross_sales) FROM retail_gold.mart_daily_sales),
         (SELECT SUM(CAST(i.quantity * i.unit_price AS DECIMAL(18, 2)))
            FROM retail_silver.order_items i JOIN sold o ON i.order_id = o.order_id)
  UNION ALL SELECT 'product gross_sales = daily gross_sales',
         (SELECT SUM(gross_sales) FROM retail_gold.mart_product_performance),
         (SELECT SUM(gross_sales) FROM retail_gold.mart_daily_sales)
  UNION ALL SELECT 'lifetime gross_sales = daily gross_sales',
         (SELECT SUM(lifetime_gross_sales) FROM retail_gold.mart_customer_lifetime_value),
         (SELECT SUM(gross_sales) FROM retail_gold.mart_daily_sales)
  UNION ALL SELECT 'daily charges = silver succeeded charges',
         (SELECT SUM(charges) FROM retail_gold.mart_daily_sales),
         (SELECT SUM(amount) FROM succeeded WHERE payment_type = 'charge')
  UNION ALL SELECT 'daily refunds = silver succeeded refunds',
         (SELECT SUM(refunds) FROM retail_gold.mart_daily_sales),
         (SELECT SUM(amount) FROM succeeded WHERE payment_type = 'refund')
  -- Payments for orders missing from silver count in daily money but belong to no customer.
  UNION ALL SELECT 'daily net - lifetime net = net of payments for unknown orders',
         (SELECT SUM(net_payments) FROM retail_gold.mart_daily_sales)
           - (SELECT SUM(lifetime_net_paid) FROM retail_gold.mart_customer_lifetime_value),
         (SELECT COALESCE(SUM(CASE WHEN payment_type = 'charge' THEN amount ELSE -amount END), 0)
            FROM succeeded WHERE order_id NOT IN (SELECT order_id FROM retail_silver.orders))
  UNION ALL SELECT 'daily rows with null business_date',
         (SELECT COUNT(*) FROM retail_gold.mart_daily_sales WHERE business_date IS NULL), 0
)
SELECT check_name, observed, expected, IF(observed = expected, 'ok', 'FAIL') AS status FROM checks;
