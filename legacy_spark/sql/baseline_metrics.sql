-- Baseline reconciliation metrics over the three reporting outputs.
-- One row per metric; every value is DECIMAL(38, 2) so legacy doubles and gold decimals compare directly.
-- Expects relations named daily_sales, customer_lifetime_value and product_performance.
-- The legacy job runs it over temp views; Phase 06 runs the same text over views on retail_gold.
-- Invariant on clean, orphan-free data: the three gross_sales totals are equal.
SELECT 'daily_sales.rows' AS metric, CAST(COUNT(*) AS DECIMAL(38, 2)) AS value FROM daily_sales
UNION ALL SELECT 'daily_sales.null_business_date_rows', CAST(COUNT_IF(business_date IS NULL) AS DECIMAL(38, 2)) FROM daily_sales
UNION ALL SELECT 'daily_sales.first_date', CAST(DATE_FORMAT(MIN(business_date), 'yyyyMMdd') AS DECIMAL(38, 2)) FROM daily_sales
UNION ALL SELECT 'daily_sales.last_date', CAST(DATE_FORMAT(MAX(business_date), 'yyyyMMdd') AS DECIMAL(38, 2)) FROM daily_sales
UNION ALL SELECT 'daily_sales.orders_placed', CAST(SUM(orders_placed) AS DECIMAL(38, 2)) FROM daily_sales
UNION ALL SELECT 'daily_sales.orders_sold', CAST(SUM(orders_sold) AS DECIMAL(38, 2)) FROM daily_sales
UNION ALL SELECT 'daily_sales.items_sold', CAST(SUM(items_sold) AS DECIMAL(38, 2)) FROM daily_sales
UNION ALL SELECT 'daily_sales.gross_sales', CAST(SUM(gross_sales) AS DECIMAL(38, 2)) FROM daily_sales
UNION ALL SELECT 'daily_sales.charges', CAST(SUM(charges) AS DECIMAL(38, 2)) FROM daily_sales
UNION ALL SELECT 'daily_sales.refunds', CAST(SUM(refunds) AS DECIMAL(38, 2)) FROM daily_sales
UNION ALL SELECT 'daily_sales.net_payments', CAST(SUM(net_payments) AS DECIMAL(38, 2)) FROM daily_sales
UNION ALL SELECT 'customer_lifetime_value.rows', CAST(COUNT(*) AS DECIMAL(38, 2)) FROM customer_lifetime_value
UNION ALL SELECT 'customer_lifetime_value.customers_with_sales', CAST(COUNT_IF(orders_sold > 0) AS DECIMAL(38, 2)) FROM customer_lifetime_value
UNION ALL SELECT 'customer_lifetime_value.orders_sold', CAST(SUM(orders_sold) AS DECIMAL(38, 2)) FROM customer_lifetime_value
UNION ALL SELECT 'customer_lifetime_value.lifetime_gross_sales', CAST(SUM(lifetime_gross_sales) AS DECIMAL(38, 2)) FROM customer_lifetime_value
UNION ALL SELECT 'customer_lifetime_value.lifetime_net_paid', CAST(SUM(lifetime_net_paid) AS DECIMAL(38, 2)) FROM customer_lifetime_value
UNION ALL SELECT 'product_performance.rows', CAST(COUNT(*) AS DECIMAL(38, 2)) FROM product_performance
UNION ALL SELECT 'product_performance.products_sold', CAST(COUNT_IF(units_sold > 0) AS DECIMAL(38, 2)) FROM product_performance
UNION ALL SELECT 'product_performance.units_sold', CAST(SUM(units_sold) AS DECIMAL(38, 2)) FROM product_performance
UNION ALL SELECT 'product_performance.gross_sales', CAST(SUM(gross_sales) AS DECIMAL(38, 2)) FROM product_performance
