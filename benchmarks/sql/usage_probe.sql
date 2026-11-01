-- Optional: usage quantities per job run and pipeline from the billing system table, last 7 days.
-- Free Edition does not bill in currency, and this table may not be readable there (benchmarks/README.md,
-- B-V3). Record quantities and units only; never convert them to a price.
SELECT usage_date,
       usage_metadata.job_run_id AS job_run_id,
       usage_metadata.dlt_pipeline_id AS pipeline_id,
       sku_name,
       usage_unit,
       round(sum(usage_quantity), 4) AS quantity
FROM system.billing.usage
WHERE usage_date >= current_date() - INTERVAL 7 DAYS
  AND (usage_metadata.job_run_id IS NOT NULL OR usage_metadata.dlt_pipeline_id IS NOT NULL)
GROUP BY ALL
ORDER BY usage_date, job_run_id;
