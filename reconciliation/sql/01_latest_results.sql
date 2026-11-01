-- Results of the latest reconciliation run, as appended by reconciliation/reconcile.py.
-- First result: one row per comparison and mart. Second: differences grouped by kind and cause.
-- Every unexplained count must be 0; an explained difference must name a cause.
USE CATALOG workspace;

SELECT run_id, dataset, legacy_dataset, causes, mart, legacy_rows, modern_rows,
       legacy_duplicate_keys, modern_duplicate_keys, missing_in_modern, missing_in_legacy,
       value_mismatches, explained, unexplained, status
FROM retail_audit.reconciliation_summary
WHERE run_id = (SELECT max_by(run_id, run_at) FROM retail_audit.reconciliation_summary)
ORDER BY legacy_dataset DESC, mart;

SELECT legacy_dataset, mart, kind, coalesce(causes, '(none)') AS causes, explained, count(*) AS keys
FROM retail_audit.reconciliation_differences
WHERE run_id = (SELECT max_by(run_id, run_at) FROM retail_audit.reconciliation_summary)
GROUP BY ALL
ORDER BY explained, legacy_dataset, mart, kind, causes;
