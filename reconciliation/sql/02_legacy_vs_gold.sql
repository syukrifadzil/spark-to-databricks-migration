-- Independent SQL cross-check of the reconciliation task: one legacy output against the three gold
-- marts. Per mart: row counts, duplicate keys, keys missing on either side, and keys whose row hash
-- differs. It does not classify differences; compare its counts with 01_latest_results.sql.
-- The legacy dataset is named in the three read_files paths. To check another one, replace
-- "/legacy/ordered/" with "/legacy/clean/" or "/legacy/anomalous/" in all three.
USE CATALOG workspace;

WITH legacy_daily AS (
  SELECT CAST(business_date AS DATE) AS k,
         sha2(to_json(named_struct(
           'orders_placed', CAST(orders_placed AS BIGINT), 'orders_sold', CAST(orders_sold AS BIGINT),
           'items_sold', CAST(items_sold AS BIGINT), 'gross_sales', CAST(gross_sales AS DECIMAL(18, 2)),
           'charges', CAST(charges AS DECIMAL(18, 2)), 'refunds', CAST(refunds AS DECIMAL(18, 2)),
           'net_payments', CAST(net_payments AS DECIMAL(18, 2)))), 256) AS h
  FROM read_files('/Volumes/workspace/retail_landing/raw/legacy/ordered/daily_sales/part-*.csv',
         format => 'csv', header => true,
         schema => 'business_date STRING, orders_placed STRING, orders_sold STRING, items_sold STRING, gross_sales STRING, charges STRING, refunds STRING, net_payments STRING')
),
gold_daily AS (
  SELECT business_date AS k,
         sha2(to_json(named_struct(
           'orders_placed', orders_placed, 'orders_sold', orders_sold, 'items_sold', items_sold,
           'gross_sales', gross_sales, 'charges', charges, 'refunds', refunds,
           'net_payments', net_payments)), 256) AS h
  FROM retail_gold.mart_daily_sales
),
legacy_clv AS (
  SELECT customer_id AS k,
         sha2(to_json(named_struct(
           'region', region, 'first_order_date', CAST(first_order_date AS DATE),
           'last_order_date', CAST(last_order_date AS DATE), 'orders_sold', CAST(orders_sold AS BIGINT),
           'lifetime_gross_sales', CAST(lifetime_gross_sales AS DECIMAL(18, 2)),
           'lifetime_net_paid', CAST(lifetime_net_paid AS DECIMAL(18, 2)))), 256) AS h
  FROM read_files('/Volumes/workspace/retail_landing/raw/legacy/ordered/customer_lifetime_value/part-*.csv',
         format => 'csv', header => true,
         schema => 'customer_id STRING, region STRING, first_order_date STRING, last_order_date STRING, orders_sold STRING, lifetime_gross_sales STRING, lifetime_net_paid STRING')
),
gold_clv AS (
  SELECT customer_id AS k,
         sha2(to_json(named_struct(
           'region', region, 'first_order_date', first_order_date, 'last_order_date', last_order_date,
           'orders_sold', orders_sold, 'lifetime_gross_sales', lifetime_gross_sales,
           'lifetime_net_paid', lifetime_net_paid)), 256) AS h
  FROM retail_gold.mart_customer_lifetime_value
),
legacy_product AS (
  SELECT product_id AS k,
         sha2(to_json(named_struct(
           'product_name', product_name, 'category', category, 'status', status,
           'units_sold', CAST(units_sold AS BIGINT), 'gross_sales', CAST(gross_sales AS DECIMAL(18, 2)),
           'orders_sold', CAST(orders_sold AS BIGINT))), 256) AS h
  FROM read_files('/Volumes/workspace/retail_landing/raw/legacy/ordered/product_performance/part-*.csv',
         format => 'csv', header => true,
         schema => 'product_id STRING, product_name STRING, category STRING, status STRING, units_sold STRING, gross_sales STRING, orders_sold STRING')
),
gold_product AS (
  SELECT product_id AS k,
         sha2(to_json(named_struct(
           'product_name', product_name, 'category', category, 'status', status,
           'units_sold', units_sold, 'gross_sales', gross_sales, 'orders_sold', orders_sold)), 256) AS h
  FROM retail_gold.mart_product_performance
),
-- One row per key on each side: how many rows it has and one of their hashes. <=> matches null keys.
pairs AS (
  SELECT 'daily_sales' AS mart, l.n AS ln, g.n AS gn, l.h AS lh, g.h AS gh
  FROM (SELECT k, count(*) AS n, min(h) AS h FROM legacy_daily GROUP BY k) l
  FULL OUTER JOIN (SELECT k, count(*) AS n, min(h) AS h FROM gold_daily GROUP BY k) g ON l.k <=> g.k
  UNION ALL
  SELECT 'customer_lifetime_value', l.n, g.n, l.h, g.h
  FROM (SELECT k, count(*) AS n, min(h) AS h FROM legacy_clv GROUP BY k) l
  FULL OUTER JOIN (SELECT k, count(*) AS n, min(h) AS h FROM gold_clv GROUP BY k) g ON l.k <=> g.k
  UNION ALL
  SELECT 'product_performance', l.n, g.n, l.h, g.h
  FROM (SELECT k, count(*) AS n, min(h) AS h FROM legacy_product GROUP BY k) l
  FULL OUTER JOIN (SELECT k, count(*) AS n, min(h) AS h FROM gold_product GROUP BY k) g ON l.k <=> g.k
)
SELECT mart,
       coalesce(sum(ln), 0) AS legacy_rows,
       coalesce(sum(gn), 0) AS gold_rows,
       count_if(ln > 1) AS legacy_duplicate_keys,
       count_if(gn > 1) AS gold_duplicate_keys,
       count_if(gn IS NULL) AS missing_in_gold,
       count_if(ln IS NULL) AS missing_in_legacy,
       count_if(ln = 1 AND gn = 1 AND lh <> gh) AS hash_mismatches
FROM pairs
GROUP BY mart
ORDER BY mart;
