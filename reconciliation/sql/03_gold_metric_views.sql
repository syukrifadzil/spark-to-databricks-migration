-- Views with the legacy output names over the gold marts, so legacy_spark/sql/baseline_metrics.sql
-- runs unchanged against gold (Phase 02 EXPLANATION section 7). Paste this file and the metrics
-- file together (runbook): the views exist only for the session that creates them.
USE CATALOG workspace;
CREATE OR REPLACE TEMPORARY VIEW daily_sales AS SELECT * FROM retail_gold.mart_daily_sales;
CREATE OR REPLACE TEMPORARY VIEW customer_lifetime_value AS SELECT * FROM retail_gold.mart_customer_lifetime_value;
CREATE OR REPLACE TEMPORARY VIEW product_performance AS SELECT * FROM retail_gold.mart_product_performance;
