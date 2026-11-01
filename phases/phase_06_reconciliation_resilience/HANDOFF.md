# Phase 06 Handoff

## Status

Complete; the commit is pending (Step 14). Every runbook step from 1 to 12, including 11b, was run on 2026-11-01. Steps 8 and 9 were run twice.

Three failures came up during the runs, and each is fixed:
- the first Step 3 rehearsal (reading the manifests)
- the first job run (the exit call)
- duplicate result rows when the platform ran a failed task a second time

The last run of each step passed. The run log separates two kinds of result:
- results transcribed from pasted output or screenshots
- results the maintainer checked against the runbook and reported as matching, without pasting the output (the final entry) The maintainer approved Phase 06 on 2026-11-01 ("Proceed") and chose two things:
- The Phase 02 legacy outputs are still on disk.
- Reconciliation runs as the third task of `retail_nightly`.

## Run log

**Step 1 (2026-11-01):** `46 passed in 25.84s`. That was before the fifth reconciliation test was added; the expected count is now 47.

**Step 2 (2026-11-01):** all three manifests present. The legacy job read, for example, 5,937 orders from 4 files for `ordered` and 5,972 from 9 files for `anomalous`.

| dataset | rows | placed | sold | gross | charges | refunds |
|---|---|---|---|---|---|---|
| ordered | 94.00 | 5300.00 | 4478.00 | 2646546.91 | 2780514.47 | 146764.64 |
| clean | 94.00 | 5300.00 | 4477.00 | 2646985.28 | 2780817.81 | 146764.64 |
| anomalous | 99.00 | 5310.00 | 4472.00 | 2644655.33 | 2782650.86 | 146764.64 |

- **`ordered`** matches the prediction (EXPLANATION section 6) in every column. Legacy `ordered` and clean-state gold are predicted to be equal, but clean-state gold has not been measured yet (Step 8).
- **`clean` and `anomalous`** match the Phase 02 recorded values.

**Step 3, first attempt (2026-11-01): failed.** Both commands stopped before any comparison, with:

```
WARN DataSource: All paths were ignored:
  file:/Users/syuk/Desktop/databricks-prep/dbx-proj/spark-to-dbx/data/raw/clean/_manifest.json
...
  File ".../reconciliation/reconcile.py", line 70, in read_json
    return json.loads(spark.read.text(path, wholetext=True).first()[0])
TypeError: 'NoneType' object is not subscriptable
```

The anomalous run failed the same way. Spark's file listing skips names that start with `_`, even when the path is given explicitly, so it read no rows. Fix: `read_json` now uses `open()`, and a new test runs `main()` end to end (EXPLANATION section 4.5). The fix adds assumption V16: `open()` works on `/Volumes` paths from a serverless task.

**Step 1, after the fix (2026-11-01):** `47 passed in 27.57s`.

**Step 3, after the fix (2026-11-01): both runs `RESULT: PASS`.** The "modern" side is the legacy `ordered` output. In both runs, the first comparison (legacy `ordered` against itself) showed 0 everywhere, as expected.

Second comparison of the clean run (legacy `clean`, causes `feed`):

| Mart | Rows legacy/modern | Duplicate keys | Missing | Mismatched | Explained | Unexplained |
|---|---|---|---|---|---|---|
| `daily_sales` | 94/94 | 0/0 | 0/0 | 3 | 3 | 0 |
| `customer_lifetime_value` | 530/530 | 0/0 | 0/0 | 7 | 7 | 0 |
| `product_performance` | 50/50 | 0/0 | 0/0 | 7 | 7 | 0 |

Totals lines, legacy then modern:
- **`daily_sales`:** orders_sold 4477 / 4478; items_sold 16242 / 16231; gross_sales 2646985.28 / 2646546.91; charges 2780817.81 / 2780514.47; net_payments 2634053.17 / 2633749.83.
  - The orders_sold, gross and charges lines match the prediction.
  - The items_sold (+11) and net_payments (+303.34, the same as charges, because refunds are equal) lines were not in the prediction but follow from the same replayed items and payments.
- **`customer_lifetime_value`:** orders_sold 4477 / 4478; lifetime_gross_sales 2646985.28 / 2646546.91; lifetime_net_paid 2634053.17 / 2633749.83.
- **`product_performance`:** units_sold 16242 / 16231; gross_sales 2646985.28 / 2646546.91; orders_sold 9121 / 9124.

Second comparison of the anomalous run (legacy `anomalous`, causes `feed, anomaly`):

| Mart | Rows legacy/modern | Duplicate keys | Missing | Mismatched | Explained | Unexplained |
|---|---|---|---|---|---|---|
| `daily_sales` | 99/94 | 1/0 | 3/0 | 21 | 24 | 0 |
| `customer_lifetime_value` | 531/530 | 0/0 | 1/0 | 30 | 31 | 0 |
| `product_performance` | 50/50 | 0/0 | 0/0 | 15 | 15 | 0 |

Totals lines, legacy then modern:
- **`daily_sales`:** orders_placed 5310 / 5300; orders_sold 4472 / 4478; items_sold 16221 / 16231; gross_sales 2644655.33 / 2646546.91; charges 2782650.86 / 2780514.47; net_payments 2635886.22 / 2633749.83.
- **`customer_lifetime_value`:** orders_sold 4472 / 4478; lifetime_gross_sales 2644655.33 / 2646546.91; lifetime_net_paid 2633122.22 / 2633749.83.
- **`product_performance`:** units_sold 16221 / 16231; gross_sales 2644655.33 / 2646546.91; orders_sold 9110 / 9124.

Reading of the anomalous result:
- **`daily_sales`:** the one duplicate legacy key is the null business date (three legacy rows, L5), which the runbook predicted. 99 rows on 97 keys leaves 3 keys missing in modern: the null date and two others.
  - My inference, not shown in the output: the other two are 2026-01-06 and 2026-01-08, the dates the `invalid_reference` and `payment_mismatch` rows add to the legacy output. `01_latest_results.sql` in Step 6 lists the keys.
- **`customer_lifetime_value`:** the one missing key is the legacy null `customer_id` row (`null_required`).

The Step 3 runs also printed `WARN FileStreamSink: Assume no metadata directory ... java.io.FileNotFoundException: File data/raw/<dataset>/batch_*/orders.csv does not exist` with a stack trace, once for each of orders, order_items and payments per comparison. Spark first tests the path literally, glob included, for a streaming metadata folder, logs that as a warning, then expands the glob. The reads worked: the touched keys explained every difference above.

**Step 6b, first attempt (2026-11-01, run 16672463981488): failed on the exit, not on the comparison.** The job ran from 10:28:10 to 10:34:24 and ended `INTERNAL_ERROR FAILED`, with `Task reconciliation failed with message: Workload failed, see run output for details`. The task error was:

```
SystemExit: 0
An exception has occurred, use %tb to see the full traceback.
```

- **What it shows:** `main()` returned 0, which it does only after `RESULT: PASS` (and after appending to `retail_audit`). The script then called `sys.exit(0)`, and the job runner reported that as a failure.
- **What it confirms:**
  - V16: `open()` read both manifests from `/Volumes`.
  - V4: the script runs as `__main__`. The report itself is not recorded yet; it is in the task output on the run page.
- **Fix:** the entry point no longer calls `sys.exit()`, and raises `RuntimeError` on failure (EXPLANATION section 4.4).
- **Not recorded for this run:**
  - Steps 4 and 5 output (upload listings, validate, deploy)
  - Step 6a layer counts

**Step 6c (2026-11-01, screenshots).**

`01_latest_results.sql`, summary for reconciliation run `1038227616284903`, dataset `anomalous`:

| Legacy | Causes | Mart | Rows legacy/gold | Dup keys | Missing in gold / in legacy | Mismatched | Explained | Unexplained |
|---|---|---|---|---|---|---|---|---|
| ordered | silver_anomaly | customer_lifetime_value | 530/530 | 0/0 | 0/0 | 5 | 5 | 0 |
| ordered | silver_anomaly | daily_sales | 94/96 | 0/0 | 0/2 | 0 | 2 | 0 |
| ordered | silver_anomaly | product_performance | 50/50 | 0/0 | 0/0 | 0 | 0 | 0 |
| anomalous | feed,anomaly | customer_lifetime_value | 531/530 | 0/0 | 1/0 | 25 | 26 | 0 |
| anomalous | feed,anomaly | daily_sales | 99/96 | 1/0 | 1/0 | 21 | 22 | 0 |
| anomalous | feed,anomaly | product_performance | 50/50 | 0/0 | 0/0 | 15 | 15 | 0 |

- **Gold against `ordered`:** as predicted in EXPLANATION section 6:
  - two dates missing in legacy
  - five customers mismatched (the prediction was "five or fewer")
  - no product differences
  - all explained
- **Gold against `anomalous`:** every difference explained.
  - `daily_sales` now has one key missing in gold, against three in the local rehearsal. Gold contains the two dates that legacy `ordered` lacks, which is consistent with those two being 2026-01-06 and 2026-01-08. This summary does not name the keys; `retail_audit.reconciliation_differences` does.
- **Differences by kind and cause:** 39 groups. The query sorts `explained` false first, and the first row is true, so no difference is unexplained.

The run id is not the one from the failed first run (16672463981488). Whether it comes from a rerun after the `sys.exit` fix has not been reported.

`02_legacy_vs_gold.sql`, legacy `ordered`:

| Mart | Legacy rows | Gold rows | Dup keys (legacy/gold) | Missing in gold | Missing in legacy | Hash mismatches |
|---|---|---|---|---|---|---|
| customer_lifetime_value | 530 | 530 | 0/0 | 0 | 0 | 5 |
| daily_sales | 94 | 96 | 0/0 | 0 | 2 | 0 |
| product_performance | 50 | 50 | 0/0 | 0 | 0 | 0 |

These equal the task's counts for the same comparison: the SQL and PySpark implementations agree (D5). V10 is confirmed: `read_files` with `schema` and a glob. The run with `/legacy/anomalous/` paths has not been reported.

Baseline metrics over gold (`03_gold_metric_views.sql` and `baseline_metrics.sql` in one run; 20 metrics). This confirms V11: temporary views are visible to later statements in the same run.

| Metric | Value |
|---|---|
| daily_sales.rows / null_business_date_rows | 96 / 0 |
| daily_sales.first_date / last_date | 20251003 / 20260108 |
| daily_sales.orders_placed / orders_sold / items_sold | 5310 / 4478 / 16231 |
| daily_sales.gross_sales / charges / refunds / net_payments | 2646546.91 / 2780589.47 / 146764.64 / 2633824.83 |
| customer_lifetime_value.rows / customers_with_sales / orders_sold | 530 / 510 / 4478 |
| customer_lifetime_value.lifetime_gross_sales / lifetime_net_paid | 2646546.91 / 2633774.83 |
| product_performance.rows / products_sold / units_sold / gross_sales | 50 / 46 / 16231 / 2646546.91 |

- **Gross sales (I6):** the three gross sales totals are equal. The headline matches Phase 05.
- **Net paid versus net payments:** lifetime net paid is 50.00 below daily net payments. My explanation, not verified per row: the `invalid_reference` payment of 50.00 for an unknown order has no customer, so it counts in `daily_sales` but not in any customer's lifetime value.

**Step 6d (2026-11-01):** `03_anomaly_checks.sql`, 18 rows, all `ok`. This covers R3, R4 and R5a:
- quarantine 35 of 35
- no silver orders from `EVT-A012`
- 5 bronze rows with rescued data

**Step 10 attempted early (2026-11-01):** `RESTORE ... TO VERSION AS OF <V_clean>` returned `[PARSE_SYNTAX_ERROR] Syntax error at or near '<'`. The placeholder was not replaced. The statement did not run, so nothing changed. Step 10 belongs after Steps 7 to 9, and V_clean comes from Step 8. The runbook now says so at Step 10.

**Step 7, R8 (2026-11-01, run 1052708769485782): failed, as designed.**
- **Run:** 12:38:31 to 12:43:41, ending `INTERNAL_ERROR FAILED` with `Task reconciliation failed with message: Workload failed`.
- **Task error:** `RuntimeError: reconciliation found unexplained differences; see the report above`, raised at `reconcile.py` line 309.
- **What it confirms:** V5. An exception fails the task and the run, and the CLI exits with an error.

Two further observations:
- **The task's report is not in the CLI output.** For a failed task the CLI printed only the error, so the `UNEXPLAINED` lines and the `FAIL` rows have not been recorded yet.
- **The traceback appears twice, from two different kernels** (`~/.ipykernel/10916` and `~/.ipykernel/12022`). The audit query below confirms the task ran twice.

**Step 8, R6 (2026-11-01).**
- **Removal:** `fs rm -r` of `batch_004` to `batch_013`. The listing shows `_anomaly_manifest.json`, `_expected`, `_manifest.json`, `batch_000` to `batch_003` and `batch_900`. That confirms V15, and that `batch_901` is not in landing.
- **Full refresh:** update `9508add7`, 04:44:40 to 04:46:58 UTC, `COMPLETED`. All 15 flows completed: 5 bronze, 5 silver and 5 quarantine.
- **Job, `dataset=clean`:** run 755100707843223, 12:49:39 to 12:52:19, `TERMINATED SUCCESS`, `RESULT: PASS`.

| Legacy | Causes | Mart | Rows legacy/gold | Dup keys | Missing | Mismatched | Explained | Unexplained |
|---|---|---|---|---|---|---|---|---|
| ordered | none (exact) | daily_sales | 94/94 | 0/0 | 0/0 | 0 | 0 | 0 |
| ordered | none (exact) | customer_lifetime_value | 530/530 | 0/0 | 0/0 | 0 | 0 | 0 |
| ordered | none (exact) | product_performance | 50/50 | 0/0 | 0/0 | 0 | 0 | 0 |
| clean | feed | daily_sales | 94/94 | 0/0 | 0/0 | 3 | 3 | 0 |
| clean | feed | customer_lifetime_value | 530/530 | 0/0 | 0/0 | 7 | 7 | 0 |
| clean | feed | product_performance | 50/50 | 0/0 | 0/0 | 7 | 7 | 0 |

- **I1 holds.** Gold in the clean state equals legacy `ordered` on every key of all three marts, with no totals lines. This is the exact match of AC10.
- **The clean block equals the Step 3 rehearsal** in every count and every totals line, with gold on the modern side instead of legacy `ordered`. That follows from I1.
- **Not recorded yet:**
  - `01_layer_counts.sql`
  - `02_silver_vs_expected.sql`
  - the headline query
  - `DESCRIBE HISTORY` and V_clean

**Step 9, R5b (2026-11-01).**
- **Upload:** the ten batches were copied back, 15 files in all. The listing shows `batch_000` to `batch_013` and `batch_900`.
- **Job:** run 1114416582176359, 13:07:25 to 13:12:35, `TERMINATED SUCCESS`, `RESULT: PASS`.

| Legacy | Causes | Mart | Rows legacy/gold | Dup keys | Missing | Mismatched | Explained | Unexplained |
|---|---|---|---|---|---|---|---|---|
| ordered | silver_anomaly | daily_sales | 94/96 | 0/0 | 0/2 | 0 | 2 | 0 |
| ordered | silver_anomaly | customer_lifetime_value | 530/530 | 0/0 | 0/0 | 5 | 5 | 0 |
| ordered | silver_anomaly | product_performance | 50/50 | 0/0 | 0/0 | 0 | 0 | 0 |
| anomalous | feed, anomaly | daily_sales | 99/96 | 1/0 | 1/0 | 21 | 22 | 0 |
| anomalous | feed, anomaly | customer_lifetime_value | 531/530 | 0/0 | 1/0 | 25 | 26 | 0 |
| anomalous | feed, anomaly | product_performance | 50/50 | 0/0 | 0/0 | 15 | 15 | 0 |

Totals lines, legacy then gold:
- **ordered block:**
  - `daily_sales`: orders_placed 5300 / 5310; charges 2780514.47 / 2780589.47; net_payments 2633749.83 / 2633824.83
  - `customer_lifetime_value`: lifetime_net_paid 2633749.83 / 2633774.83
- **anomalous block, `daily_sales`:** orders_sold 4472 / 4478; items_sold 16221 / 16231; gross_sales 2644655.33 / 2646546.91; charges 2782650.86 / 2780589.47; net_payments 2635886.22 / 2633824.83
- **anomalous block, `customer_lifetime_value`:** orders_sold 4472 / 4478; lifetime_gross_sales 2644655.33 / 2646546.91; lifetime_net_paid 2633122.22 / 2633774.83
- **anomalous block, `product_performance`:** units_sold 16221 / 16231; gross_sales 2644655.33 / 2646546.91; orders_sold 9110 / 9124

What the run shows:
- **Same counts as Step 6:** every count equals the Step 6c summary (run 1038227616284903). The gold side of the totals equals the Phase 05 anomalous headline: placed 5,310, charges 2,780,589.47, net 2,633,824.83.
- **Gold returned to the anomalous state** after the re-delivery, which partly confirms V14.
- **Not recorded yet:**
  - `01_layer_counts.sql` and its fingerprints. Step 6a was not recorded, so the Phase 05 Step 7 counts are the reference.
  - `03_anomaly_checks.sql`
  - the headline query

**Audit and history queries (2026-11-01, screenshots).**

Writes per run in `reconciliation_summary`:

| Run | Dataset | Summary rows | Writes | First write (UTC) | Run outcome |
|---|---|---|---|---|---|
| 16672463981488 | anomalous | 12 | 2 | 02:32:51 | Failed (`SystemExit: 0`) |
| 1038227616284903 | anomalous | 6 | 1 | 03:58:46 | Rerun after the exit fix; 6c showed all `ok` |
| 1052708769485782 | clean | 12 | 2 | 04:42:36 | Failed (Step 7, as designed) |
| 755100707843223 | clean | 6 | 1 | 04:52:04 | PASS (Step 8) |
| 1114416582176359 | anomalous | 6 | 1 | 05:12:17 | PASS (Step 9) |

- **Finding:** each failed run executed the reconciliation task twice under the same run id. Each time, the task wrote a full set of results and failed again. The job sets no retries, so the second attempt came from the platform. I have not found where that behaviour is documented. Successful runs wrote once.
- **Effect:** those two runs have every row twice. The differences table has no `run_at`, so the two sets cannot be told apart.
- **Fix:** `write_results` now deletes the run id's rows before appending (EXPLANATION section 4.4). It is deployed in Step 10 and checked in Step 11b.
- **The existing duplicate rows are kept** as the record of this finding. Read the counts below as one set.

Step 7 summary (run 1052708769485782). Each row appears twice, so one set is shown:

| Legacy | Mart | Missing in gold / in legacy | Mismatched | Explained | Unexplained | Status |
|---|---|---|---|---|---|---|
| ordered | customer_lifetime_value | 0/0 | 5 | 0 | 5 | FAIL |
| ordered | daily_sales | 0/2 | 0 | 0 | 2 | FAIL |
| ordered | product_performance | 0/0 | 0 | 0 | 0 | ok |
| clean | customer_lifetime_value | 0/0 | 12 | 7 | 5 | FAIL |
| clean | daily_sales | 0/2 | 3 | 3 | 2 | FAIL |
| clean | product_performance | 0/0 | 7 | 7 | 0 | ok |

The unexplained keys are the same in both blocks, and none has a cause. There are 28 rows: 14 keys, each written twice.
- **`daily_sales`, `missing_in_legacy`:** 2026-01-06 and 2026-01-08.
- **`customer_lifetime_value`, `value_mismatch`:** CUST-000093, CUST-000242, CUST-000329, CUST-000382 and CUST-000389.

What this shows for R8:
- **The test passed.** The exact comparison flagged exactly the keys that the two silver-changing scenarios (`invalid_reference`, `payment_mismatch`) produce, and nothing else.
- **The same keys are explained elsewhere.** The anomalous plan explains these keys through `silver_anomaly` (Steps 6c and 9: 2 dates and 5 customers). In the clean block, the 7 clean-feed differences stay explained, and only the 5 + 2 new keys fail.
- **The dates match the prediction** in EXPLANATION section 6. The prediction for customers was "five or fewer"; there were five.

`DESCRIBE HISTORY workspace.retail_gold.mart_daily_sales` showed 8 versions, every one a `CREATE OR REPLACE TABLE AS SELECT`, one per dbt build. The `job` column ties each version to its job run:

| Version | Timestamp (UTC) | Job run |
|---|---|---|
| 7 | 2026-11-01 05:10:44 | 1114416582176359 (Step 9) |
| 6 | 2026-11-01 04:51:23 | 755100707843223 (Step 8, clean state) |
| 5 | 2026-11-01 04:41:25 | 1052708769485782 (Step 7) |
| 4 | 2026-11-01 03:57:11 | 1038227616284903 |
| 3 | 2026-11-01 02:31:17 | 16672463981488 |
| 2 | 2026-10-31 17:36:10 | 152633966783378 (Phase 05) |
| 1, 0 | 2026-10-31 17:07:23, 15:02:31 | none (manual dbt builds, Phase 04) |

- **V_clean = 6.**
- **V12 is partly confirmed:** a replaced table keeps its history. `RESTORE` is still to run.

**Step 1, after the write fix (2026-11-01):** `47 passed in 28.06s`. This does not cover the new write path, which needs Delta.

**Step 10 deploy:** `Files: 6 uploaded, 0 deleted`; `Resources: 0 created, 0 changed, 0 deleted, 2 unchanged`.

**Step 10 roll forward (run 948716019579544, 17:13:59 to 17:16:50): `TERMINATED SUCCESS`, `RESULT: PASS`.**
- Only `gold` and `reconciliation` ran, so `--only gold+` works.
- Every count and totals line equals Step 9.
- `Results written to ...` shows the new script ran. Its write path (`tableExists`, then `DELETE`, then append) succeeded, which partly confirms V17.
- **The restore before it** is recorded below: history version 8. The headline after the restore was not captured.

**Step 11b (run 198333840649456, 17:19:27 to 17:23:53): failed, as designed.** The task raised the same `RuntimeError`, now at line 315.
- The traceback again comes from two kernels, `11108` and `12221`, so the task ran twice once more.
- Whether the second attempt replaced the first one's rows is not recorded yet; the writes-per-run query checks it.

**Step 12, R2 (run 164609088443697, 17:25:52 to 17:30:38): `TERMINATED SUCCESS`, `RESULT: PASS`.**
- **Upload:** `batch_002` from the clean feed was copied to `batch_902` (5 files).
- **Reconciliation:** every count and totals line equals Steps 9 and 10. The replay did not change gold.
- **Not recorded:** `01_layer_counts.sql`, the bronze growth and the silver counts.

**Step 11 (R1, plain rerun):** not run yet.

**Checks after Steps 10 to 12 (2026-11-01, screenshots).**

Writes per run. The five earlier runs are as recorded above.

| Run | Dataset | Summary rows | Writes | First write (UTC) |
|---|---|---|---|---|
| 948716019579544 | anomalous | 6 | 1 | 09:16:31 |
| 198333840649456 | clean | 6 | 1 | 09:23:34 |
| 164609088443697 | anomalous | 6 | 1 | 09:30:19 |

What the 11b checks show:
- **The fix works.** In Step 11b the task again ran twice (two kernels), yet its run has one set of results.
- **The rows come from the second attempt.** The single write is at 09:23:34, 19 seconds before the run ended at 09:23:53, so the second attempt replaced the first one's rows.
- **Unexplained difference rows for the run: 14.** That is 7 keys in each of the two comparisons, against 28 in Step 7.
- **V17 is confirmed.**

`DESCRIBE HISTORY workspace.retail_gold.mart_daily_sales LIMIT 5`:

| Version | Timestamp (UTC) | Operation | Job run |
|---|---|---|---|
| 11 | 09:29:15 | CREATE OR REPLACE TABLE AS SELECT | 164609088443697 (Step 12) |
| 10 | 09:22:07 | CREATE OR REPLACE TABLE AS SELECT | 198333840649456 (Step 11b) |
| 9 | 09:14:53 | CREATE OR REPLACE TABLE AS SELECT | 948716019579544 (Step 10 roll forward) |
| 8 | 09:12:48 | RESTORE, `{"version":"6","timestamp":null}` | none (SQL editor) |
| 7 | 05:10:44 | CREATE OR REPLACE TABLE AS SELECT | 1114416582176359 (Step 9) |

- **`RESTORE` was run and accepted, so V12 is confirmed.** Version 8 is the restore to version 6. The roll forward then rebuilt the table as version 9.
- **Not captured:** the headline right after the restore. Time travel to version 8 can recover it (runbook Step 10 note).

**Silver time travel attempt (2026-11-01): not supported.** A count of the silver and quarantine tables `TIMESTAMP AS OF '2026-11-01T05:00:00Z'` failed with `assertion failed: The reconciliation query was not resolved for the StreamingTable or MaterializedView`.
- "Reconciliation" in that message is the platform's own term, not this project's task.
- The tables published by the pipeline did not accept time travel here, so the clean-state silver evidence for R6 cannot be recovered after the fact.
- Steps 8 and 9 are repeated to capture it (next entries).

Headline now, after Step 12: 96 / 5,310 / 4,478 / 2,646,546.91 / 2,780,589.47 / 146,764.64 / 2,633,824.83. That is the anomalous row, so neither the roll forward nor the replay changed gold.

**Final runs (2026-11-01), as reported by the maintainer.** The maintainer ran the remaining sequence below and reported that every result matched the runbook's expected values. The output was not pasted, so the expected values below are what was checked, not a transcript.
1. **Gold time travel (R7):**
   - versions 6 and 8: the clean headline, 94 rows, charges 2,780,514.47
   - version 9: the anomalous headline
   - `differing_rows` between versions 6 and 8: 0
2. **Step 12 state (R2):**
   - bronze 590 / 11,317 / 6,614 / 6,152 / 59
   - silver 530 / 10,895 / 5,310 / 5,911 / 50
   - quarantine 5 / 5 / 10 / 15 / 0
   - 18 anomaly checks `ok`
   - fingerprints kept as the reference
3. **Step 11 (R1):** job PASS; counts and fingerprints identical to item 2.
4. **Step 8 repeated (R6):** listing without `batch_004` to `batch_013`. After the full refresh:
   - bronze 580 / 11,302 / 6,584 / 6,122 / 59
   - silver 530 / 50 / 5,300 / 10,885 / 5,901
   - quarantine 0
   - `02_silver_vs_expected`: every missing and unexpected count 0
5. **Step 9 repeated (R5b):** job PASS; counts and fingerprints identical to item 2; 18 anomaly checks `ok`.

This confirms V13 and V14, and supplies the R6 silver evidence and the R5b fingerprint comparison that the first pass of Steps 8 and 9 lacked.

## Files created or changed

| File | Change |
|---|---|
| `reconciliation/reconcile.py`, `reconciliation/__init__.py` | New: reconciliation engine and job entry point. Results are replaced per run id, so a second attempt of the task does not duplicate them |
| `reconciliation/sql/01_latest_results.sql`, `02_legacy_vs_gold.sql`, `03_gold_metric_views.sql` | New: SQL editor results, independent cross-check, metrics over gold |
| `tests/unit/test_reconcile.py` | New: 5 tests on local Spark |
| `tests/unit/test_bundle.py` | New test: job `python_file` paths exist |
| `databricks.yml` | Job parameter `dataset`, task `reconciliation`, environment `reconciliation` |
| `docs/diagrams/resilience-sequence.svg` | New |
| `docs/diagrams/reconciliation.svg`, `delivery.svg`, `phase-plan.svg` | Updated for the task; Phases 05 and 06 complete |
| `docs/architecture.md` | Audit schema, landing rule exception, orchestration, reconciliation and recovery sections |
| `README.md` | Status, phase table, layout, runbook link |
| `phases/phase_06_reconciliation_resilience/*.md` | Explanation, runbook, checklist, this handoff |

## Decisions taken in this phase

- Compare key by key with row hashes, and explain differences only through keys that a documented cause touches (EXPLANATION D1, D2).
- The exact match is against legacy `ordered`, because the legacy job is wrong on the clean feed by design (D3).
- Get the clean state by removing the anomaly batches and running a full refresh. This doubles as the recovery and late-delivery tests (D4).
- The task is a PySpark script; SQL is a second, independent check (D5). Results go to the new schema `retail_audit` (D6).

## Outstanding assumptions

None open. EXPLANATION section 8 has V1 to V3 verified against the documentation, and V4 to V17 confirmed by the runs of 2026-11-01. V13 and V14 are confirmed by the maintainer's report on the final runs.

`batch_901` (Phase 03 Step 11a) is not in landing: the Step 8 and 9 listings do not show it.

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| The exact-match prediction (section 6) is wrong | AC10 not met as designed | Step 2 checks the legacy `ordered` metrics locally before the workspace; any difference is a finding to explain, not to tune |
| A touch rule is too narrow | False unexplained differences | Step 3 rehearsal on real data; the unit test on the anomalous sample |
| A touch rule is too wide | A real defect hidden on a touched key | Exact comparison with no causes; the `ordered` comparison on anomalous data allows only silver-changing scenarios |
| Run stops between Steps 8 and 9 | Workspace left in the clean state | Runbook "Getting back to the anomalous state" |
| Python task cannot run on Free Edition serverless | No reconciliation in the job | Local rehearsal still runs; fallback is a notebook task calling `main([...])` (EXPLANATION section 10) |

## Human outputs required

- Step 1: recorded above (47 after the fix)
- Step 2: recorded above
- Step 3: recorded above (PASS after the fix)
- Step 4: not pasted. Later listings show `batch_901` absent.
- Step 5: not pasted. The Step 10 deploy output is recorded, and every job run shows the deployed task.
- Step 6: 6b, 6c (except `02_legacy_vs_gold` on anomalous paths) and 6d recorded. 6a not recorded; Step 12's counts became the reference instead.
- Steps 7 to 12 and 11b: recorded above. The final runs are recorded as reported, without the output.
- Step 14: committed as `df9334f` and pushed to `main` (2026-11-01). The path check, secret scan and email check printed nothing to fix. CI run result: not reported.
- Any failures, with the full output: recorded above

## Phase 07 prerequisites

1. Phase 06 complete and committed, with the test matrix filled from recorded runs.
2. Decide which runs Phase 07 benchmarks, and how:
   - the legacy job locally (`time`, `duration_seconds`)
   - the job's task durations from the run page
   - whether to add the medium preset
3. A licence choice for publication (README).
4. Explicit approval to start Phase 07.
