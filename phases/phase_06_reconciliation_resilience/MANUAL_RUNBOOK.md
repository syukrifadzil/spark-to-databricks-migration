# Phase 06 Manual Runbook: Reconciliation and Resilience

All steps are run by the maintainer. None of these commands have been run by the author. Record the actual output of every step in `HANDOFF.md`, and the test matrix evidence in `VALIDATION_CHECKLIST.md`. Paste failures in full. Every expected number is a prediction (EXPLANATION section 6); a different number is a finding, so record it and don't adjust the expectation.

**Working directory and environment for every terminal step:**

```bash
cd ~/Desktop/databricks-prep/dbx-proj/spark-to-dbx
source .venv/bin/activate
set -a; source .env; set +a
PIPELINE_ID=65b949fd-556c-47bd-ac1f-08855e9f7bd4
```

SQL steps run in the workspace SQL Editor, on "Serverless Starter Warehouse": `pbcopy < <file>`, paste, then **Run all**.

**Headline query.** Several steps compare it:

```sql
SELECT COUNT(*) AS rows, SUM(orders_placed) AS placed, SUM(orders_sold) AS sold, SUM(gross_sales) AS gross,
       SUM(charges) AS charges, SUM(refunds) AS refunds, SUM(net_payments) AS net
FROM workspace.retail_gold.mart_daily_sales;
```

| State | rows | placed | sold | gross | charges | refunds | net |
|---|---|---|---|---|---|---|---|
| Anomalous (recorded, Phase 05) | 96 | 5,310 | 4,478 | 2,646,546.91 | 2,780,589.47 | 146,764.64 | 2,633,824.83 |
| Clean (predicted) | 94 | 5,300 | 4,478 | 2,646,546.91 | 2,780,514.47 | 146,764.64 | 2,633,749.83 |

**Order matters.** Steps 6 to 11 move the workspace between states (EXPLANATION section 7). If a step fails part way, the "Getting back to the anomalous state" section at the end restores it.

## Step 1. Local unit tests

```bash
python -m pytest -q
```

Expected: `47 passed`. That is the 41 from Phase 05, plus:
- five in `tests/unit/test_reconcile.py`
- one new in `tests/unit/test_bundle.py`

The first run recorded `46 passed`, before `test_main_reads_the_manifests_and_passes_on_identical_outputs` was added after the Step 3 failure (HANDOFF, run log).

The reconciliation tests run the legacy job twice on the committed samples, so the whole run takes longer than before.

If `test_anomaly_batches_explain_every_legacy_difference` fails, its message lists the unexplained differences. Paste it: it means a cause-to-key rule is missing.

## Step 2. Refresh the legacy outputs

The three legacy outputs must come from the current job code. `output/legacy/clean` dates from before the Phase 02 O1 fix, which did not change the written files, but rerunning costs seconds and removes the doubt.

```bash
ls data/raw/clean/_manifest.json data/raw/anomalous/_anomaly_manifest.json data/raw/ordered/_manifest.json
```

If `data/raw/ordered` is missing, create it first (Phase 02 Step 8):

```bash
python -m data.generators.generate --preset small --late-rate 0 --replay-rate 0 --out data/raw/ordered
python -m data.generators.validate --data data/raw/ordered
```

Then:

```bash
for d in ordered clean anomalous; do
  python -m legacy_spark.retail_nightly_job --input data/raw/$d --output output/legacy/$d
done
python - <<'EOF'
import json
keys = ("daily_sales.rows", "daily_sales.orders_placed", "daily_sales.orders_sold",
        "daily_sales.gross_sales", "daily_sales.charges", "daily_sales.refunds")
print("dataset    " + "  ".join(k.split(".")[1] for k in keys))
for d in ("ordered", "clean", "anomalous"):
    m = json.load(open(f"output/legacy/{d}/baseline_metrics.json"))["metrics"]
    print(f"{d:<10} " + "  ".join(m[k] for k in keys))
EOF
```

Expected:

| dataset | rows | placed | sold | gross | charges | refunds | Source |
|---|---|---|---|---|---|---|---|
| ordered | 94.00 | 5300.00 | 4478.00 | 2646546.91 | 2780514.47 | 146764.64 | Predicted to equal clean gold (I1); recorded 2026-11-01 as predicted |
| clean | 94.00 | 5300.00 | 4477.00 | 2646985.28 | 2780817.81 | 146764.64 | Recorded in Phase 02 |
| anomalous | 99.00 | 5310.00 | 4472.00 | 2644655.33 | 2782650.86 | 146764.64 | Recorded in Phase 02 (charges: clean plus 1,833.05) |

The `ordered` row is the first real test of the exact-match prediction. If it differs, paste it before going on.

## Step 3. Local rehearsal

This runs the reconciliation on your machine, with no workspace involved:
- **"Modern" side:** the legacy `ordered` output, which stands in for correct gold.
- **Causes:** the same manifests as the workspace task.

```bash
python -m reconciliation.reconcile --dataset clean --landing data/raw/clean \
  --legacy-root output/legacy --modern-csv output/legacy/ordered
python -m reconciliation.reconcile --dataset anomalous --landing data/raw/anomalous \
  --legacy-root output/legacy --modern-csv output/legacy/ordered
```

Expected:
- Each run ends with `RESULT: PASS`.
- **First block (legacy `ordered` vs modern):** compares `ordered` with itself, so all counts are 0. This only shows the plumbing.
- **Second block of the clean run (legacy `clean` vs modern):** explained differences, `unexplained 0`. Predicted totals lines:
  - `daily_sales`: `total orders_sold: legacy 4477, modern 4478`, `total gross_sales: legacy 2646985.28, modern 2646546.91` and `total charges: legacy 2780817.81, modern 2780514.47`
- **Second block of the anomalous run:** explained differences on all three marts, `unexplained 0`. `daily_sales` shows at least one duplicate legacy key: the null-date rows.

Paste both outputs in full. Spark start-up makes each run take tens of seconds.

Each run also logs `WARN FileStreamSink: Assume no metadata directory ... FileNotFoundException: File data/raw/<dataset>/batch_*/orders.csv does not exist` with a long stack trace, once for each of orders, order_items and payments per comparison. This is expected and harmless. Spark first checks the path literally, glob included, then expands the glob and reads the files. The recorded run (HANDOFF) shows these warnings next to a passing result.

If a run stops with `WARN DataSource: All paths were ignored: .../_manifest.json` and `TypeError: 'NoneType' object is not subscriptable`, the script predates the fix that reads the manifests with `open()` (Spark's file listing skips names that start with `_`). Pull the current `reconciliation/reconcile.py` and rerun Step 1 first.

## Step 4. Upload the legacy outputs and the anomaly manifest

```bash
for d in ordered clean anomalous; do
  databricks fs cp -r --overwrite output/legacy/$d dbfs:/Volumes/workspace/retail_landing/raw/legacy/$d
done
databricks fs cp --overwrite data/raw/anomalous/_anomaly_manifest.json \
  dbfs:/Volumes/workspace/retail_landing/raw/retail/_anomaly_manifest.json
databricks fs ls dbfs:/Volumes/workspace/retail_landing/raw/legacy
databricks fs ls dbfs:/Volumes/workspace/retail_landing/raw/legacy/ordered
databricks fs ls dbfs:/Volumes/workspace/retail_landing/raw/legacy/ordered/daily_sales
databricks fs ls dbfs:/Volumes/workspace/retail_landing/raw/retail
```

Expected:
- **`legacy`:** `anomalous`, `clean` and `ordered`.
- **`legacy/ordered`:** `baseline_metrics.json`, `customer_lifetime_value`, `daily_sales` and `product_performance`.
- **`daily_sales`:** a `part-*.csv` file, plus `_SUCCESS` and `.crc` files, which Spark ignores.
- **`retail`:** `_anomaly_manifest.json`, `_expected`, `_manifest.json`, `batch_000` to `batch_013` and `batch_900`.
  - The bronze counts recorded in Phase 05 match the landing without `batch_901`, the Phase 03 Step 11a replay. Note whether `batch_901` is listed: Steps 6a, 8 and 12 give the expected counts for both cases.

If the listing shows `legacy/ordered/ordered/...`, the copy nested the folder (Phase 03 Step 4 saw the opposite). Remove `legacy` with `databricks fs rm -r dbfs:/Volumes/workspace/retail_landing/raw/legacy` and repeat with the target path adjusted.

`raw/legacy/` is outside `raw/retail/`, so the pipeline never reads it.

## Step 5. Validate and deploy the bundle

```bash
databricks bundle validate
databricks bundle validate -o json | python -c '
import json, sys
j = json.load(sys.stdin)["resources"]["jobs"]["retail_nightly"]
print(j["parameters"])
t = j["tasks"][2]
print(t["task_key"], t["depends_on"], t["environment_key"])
print(t["spark_python_task"])
print(j["environments"][1])'
databricks bundle deploy --fail-on-active-runs
databricks bundle summary
```

Expected:
- `Validation OK!`.
- `[{'default': 'anomalous', 'name': 'dataset'}]`.
- `reconciliation [{'task_key': 'gold'}] reconciliation`.
- **`spark_python_task`:**
  - `python_file` ends in `.../dev/files/reconciliation/reconcile.py`
  - the parameters show `{{job.parameters.dataset}}`, the volume paths, `workspace.retail_gold`, `workspace.retail_audit` and `{{job.run_id}}`
- `{'environment_key': 'reconciliation', 'spec': {'environment_version': '4'}}`.
- **`deploy`:** `Updated jobs.retail_nightly`, and the pipeline unchanged. `0 deleted`.

A `validate` warning or a `deploy` error about the environment means V6 is false: paste it.

## Step 6. Anomalous baseline: R3, R4, R5a, and AC10 on anomalous data

### 6a. Record the state before

Run `lakeflow/validation/01_layer_counts.sql`. Expected: the numbers recorded in Phase 05 Step 7.

| entity | bronze | silver | quarantine |
|---|---|---|---|
| customers | 574 | 530 | 5 |
| order_items | 11,111 | 10,895 | 5 |
| orders | 6,293 | 5,310 | 10 |
| payments | 6,043 | 5,911 | 15 |
| products | 57 | 50 | 0 |

If Step 4 listed `batch_901`, bronze is higher by one copy of `batch_002`: 590 / 11,317 / 6,614 / 6,152 / 59. Silver and quarantine are the same either way.

Paste what you see: **the result of 6a is the reference for Steps 9 and 11**, whatever it is. Keep the five fingerprints.

### 6b. Run the job

```bash
databricks bundle run retail_nightly
```

Expected:
- **Command:** prints the run URL, waits, and ends with `TERMINATED SUCCESS`.
- **On the run page:** three tasks, `bronze_silver`, `gold` and `reconciliation`, all succeeded.

Open the `reconciliation` task's output. Expected: the report from EXPLANATION section 4.4, ending with `Results written to workspace.retail_audit...` and `RESULT: PASS`. Runs before the Step 11b fix print `appended` instead.
- **`ordered` block** (gold vs legacy `ordered`):
  - `daily_sales`: `missing 0/2` (two keys missing in legacy: 2026-01-06 and 2026-01-08), explained 2.
  - `customer_lifetime_value`: up to 5 mismatched, explained.
  - `product_performance`: no differences.
  - `unexplained 0` everywhere.
- **`anomalous` block:** explained differences on all three marts, `unexplained 0`.

No report in the output (V4), or a task failure: paste the output and see troubleshooting.

A failure with only `SystemExit: 0` means the deployed script still ends with `sys.exit()`, the first version. The first run on 2026-11-01 failed this way (HANDOFF). Redeploy (Step 5) and run again.

### 6c. Reconciliation evidence in SQL

1. **`reconciliation/sql/01_latest_results.sql`.**
   - First result: six rows (two comparisons × three marts), all `ok`, all `unexplained` 0.
   - Second result: the differences grouped by kind and cause. Every row has `explained` true.
2. **`reconciliation/sql/02_legacy_vs_gold.sql`, run twice:**
   - as written (legacy `ordered`)
   - after replacing `/legacy/ordered/` with `/legacy/anomalous/` in all three paths

   Expected: its counts equal the task's counts for the same comparison:
   - `missing_in_gold` matches `missing_in_modern`
   - `hash_mismatches` matches `value_mismatches`
   - the duplicate key counts match

   Two independent implementations agreeing is the evidence (EXPLANATION D5).
3. **Baseline metrics over gold:**

   ```bash
   cat reconciliation/sql/03_gold_metric_views.sql legacy_spark/sql/baseline_metrics.sql | pbcopy
   ```

   Paste and **Run all**. Expected: 20 metrics.
   - `daily_sales.rows` 96, `null_business_date_rows` 0, `orders_placed` 5310, `orders_sold` 4478.
   - The three gross sales metrics are equal, at 2646546.91.
   - Paste the whole result: it is the gold column of the legacy versus gold metric comparison.

   If the views are not found (V11), run the view statements and the metrics query in separate tabs of the same SQL editor session, or replace the three names in the metrics query with the `retail_gold.mart_*` tables.

### 6d. Bad records, schema drift and late versions

Run `lakeflow/validation/03_anomaly_checks.sql`. Expected: 18 rows, all `ok`. This covers:
- **R3:** the quarantine counts match the manifest.
- **R4:** `schema_evolution` rows: rescued data in bronze, unchanged values in silver.
- **R5a:** `late_arrival`: no silver row from `EVT-A012`.

## Step 7. R8: reconciliation catches a defect

The workspace holds the anomalous feed, but this run claims it holds the clean feed. The exact comparison must find the two new dates and the overpaid customers, and fail.

```bash
databricks bundle run retail_nightly --params dataset=clean
```

Expected:
- The command ends with an error. On the run page, `bronze_silver` and `gold` succeeded and `reconciliation` failed.
- **Task output:**
  - The `ordered` block shows `daily_sales` with 2 unexplained `missing_in_legacy` keys (2026-01-06 and 2026-01-08), and `customer_lifetime_value` with up to 5 unexplained mismatches.
  - The `clean` block shows unexplained differences on the same keys, because only the clean-feed causes are allowed there.
  - Both are listed as `UNEXPLAINED ...` lines, and the output ends with `RESULT: FAIL`.
- **`01_latest_results.sql`:** `FAIL` rows for this run.

- **The task error:** `RuntimeError: reconciliation found unexplained differences; see the report above`.

If the task succeeds instead, V5 is false: an exception does not fail the task. Paste the output.

For a failed task, the CLI prints only the error, not the report. Read the report on the run page, in the `reconciliation` task's output. `01_latest_results.sql` shows the same counts until a later run appends new rows. After that, filter on this run's id instead of the `max_by` subquery.

## Step 8. R6: recovery from bad batches

Remove the ten anomaly batches from landing, rebuild from what remains, and check that silver and gold are back to the clean state.

```bash
for b in batch_004 batch_005 batch_006 batch_007 batch_008 batch_009 batch_010 batch_011 batch_012 batch_013; do
  databricks fs rm -r dbfs:/Volumes/workspace/retail_landing/raw/retail/$b
done
databricks fs ls dbfs:/Volumes/workspace/retail_landing/raw/retail
databricks bundle run retail_bronze_silver --full-refresh-all
```

Expected:
- **Listing:** `_anomaly_manifest.json`, `_expected`, `_manifest.json`, `batch_000` to `batch_003`, `batch_900`, and `batch_901` if Step 4 listed it.
- **Full refresh:** the command waits and ends with the update completed.

Then, in the SQL editor, before anything else runs. The silver and quarantine tables are pipeline streaming tables, and they refused time travel (HANDOFF). So this state can be measured only while it lasts.

1. **`01_layer_counts.sql`:**

   | entity | bronze | silver | quarantine |
   |---|---|---|---|
   | customers | 564 | 530 | 0 |
   | order_items | 11,096 | 10,885 | 0 |
   | orders | 6,263 | 5,300 | 0 |
   | payments | 6,013 | 5,901 | 0 |
   | products | 57 | 50 | 0 |

   Bronze is the clean feed plus one copy of `batch_002` (Phase 03 Step 9). With `batch_901` present, or `batch_902` from Step 12, it is 580 / 11,302 / 6,584 / 6,122 / 59. Each of them is one more copy of `batch_002`. Silver is the generator's expected state.
2. **`02_silver_vs_expected.sql`:** `expected_rows` 530, 50, 5,300, 10,885 and 5,901, with every `missing_from_silver` and `unexpected_in_silver` at 0.

Then rebuild gold and reconcile the clean state:

```bash
databricks bundle run retail_nightly --params dataset=clean
```

Expected:
- `TERMINATED SUCCESS`, and `RESULT: PASS` in the task output.
- **`ordered` block (the exact comparison, I1):** every count is 0 on all three marts, with no totals lines.
- **`clean` block:** explained differences only. Its totals lines match the Step 3 prediction.
- **Headline query:** the clean row of the table at the top.

Record the clean gold version for Step 10:

```sql
DESCRIBE HISTORY workspace.retail_gold.mart_daily_sales LIMIT 3;
```

Note the `version` of the top row and its `operation`. That number is V_clean: Step 10 uses it in place of `<V_clean>`.

## Step 9. R5b: late delivery of whole batches

Put the ten batches back. They arrive after the rebuild, so the next incremental update reads them as new files.

```bash
for b in batch_004 batch_005 batch_006 batch_007 batch_008 batch_009 batch_010 batch_011 batch_012 batch_013; do
  databricks fs cp -r data/raw/anomalous/$b dbfs:/Volumes/workspace/retail_landing/raw/retail/$b
done
databricks fs ls dbfs:/Volumes/workspace/retail_landing/raw/retail
databricks bundle run retail_nightly
```

Expected:
- **Listing:** as in Step 4.
- **Job:** `TERMINATED SUCCESS`, `RESULT: PASS`, and the same reconciliation counts as Step 6b.
- **`01_layer_counts.sql`:** identical to Step 6a, every count and all five fingerprints (V14, I4).
- **`03_anomaly_checks.sql`:** 18 rows, all `ok`.
- **Headline:** the anomalous row.

## Step 10. R7: gold rollback and roll forward

First, deploy the current `reconcile.py`. Its writes now replace a run's rows instead of appending a second set (EXPLANATION section 4.4):

```bash
databricks bundle deploy --fail-on-active-runs
```

Expected: `Deployment complete!`. The roll forward below is then the first run of the new write path.

Run this only after Steps 7 to 9. `<V_clean>` is a placeholder: replace it, angle brackets included, with the version number you noted in Step 8, for example `TO VERSION AS OF 7`. Left as it is, the statement fails with `PARSE_SYNTAX_ERROR ... at or near '<'` and changes nothing.

```sql
DESCRIBE HISTORY workspace.retail_gold.mart_daily_sales LIMIT 5;
RESTORE TABLE workspace.retail_gold.mart_daily_sales TO VERSION AS OF <V_clean>;
```

Then run the headline query. Expected: the clean row (94 rows, charges 2,780,514.47). The mart is now deliberately behind silver.

If `DESCRIBE HISTORY` shows only one version, or `RESTORE` is refused, V12 is false. Record it and skip to the roll forward below; the rebuild is then the only rollback route.

Roll forward by rebuilding gold from silver, followed by reconciliation:

```bash
databricks bundle run retail_nightly --only gold+
```

Expected:
- Only `gold` and `reconciliation` run, both succeed, and the task output shows `RESULT: PASS`.
- **Headline:** the anomalous row again.

If `--only gold+` is rejected, run `databricks bundle run retail_nightly --only gold,reconciliation`.

If a headline was missed, read it from history afterwards. Time travel to the restore's version (`RESTORE` in `operation`) and the version before it:

```sql
SELECT 'restored' AS state, COUNT(*) AS rows, SUM(charges) AS charges, SUM(net_payments) AS net
FROM workspace.retail_gold.mart_daily_sales VERSION AS OF <restore version>
UNION ALL
SELECT 'rolled forward', COUNT(*), SUM(charges), SUM(net_payments)
FROM workspace.retail_gold.mart_daily_sales VERSION AS OF <restore version + 1>;
```

This works only while the old data files are still kept: 7 days by default, unless a `VACUUM` has removed them.

## Step 11. R1: rerun with no new files

```bash
databricks bundle run retail_nightly
```

Expected:
- `TERMINATED SUCCESS` and `RESULT: PASS`.
- `01_layer_counts.sql` identical to Step 6a, or to Step 9 if 6a was not recorded. Step 9 is the state just before this rerun, so it is the closer reference for R1 anyway.
- The headline identical to the anomalous row.

## Step 11b. R8 again: one set of results per run

In Step 7, the failed task ran twice and wrote its results twice under one run id (HANDOFF). Repeat the negative test with the deployed fix:

```bash
databricks bundle run retail_nightly --params dataset=clean
```

Expected: the same failure as Step 7. Then:

```sql
SELECT run_id, dataset, count(*) AS summary_rows, count(DISTINCT run_at) AS writes, min(run_at) AS first_write
FROM workspace.retail_audit.reconciliation_summary
GROUP BY ALL ORDER BY first_write;
```

Expected for the new run: 6 summary rows and 1 write.
- If the CLI shows the traceback twice again, the task ran twice and the second attempt replaced the first one's rows.
- A task error in `write_results` means V17 is false. Paste it.

This run rebuilds gold from unchanged silver, so gold is left as it was.

## Step 12 (optional). R2: replayed batch

```bash
databricks fs cp -r data/raw/clean/batch_002 dbfs:/Volumes/workspace/retail_landing/raw/retail/batch_902
databricks bundle run retail_nightly
```

Expected in `01_layer_counts.sql`:
- **Bronze:** Step 6a's counts plus 16 customers, 206 items, 321 orders, 109 payments and 2 products. Without `batch_901` that gives 590 / 11,317 / 6,614 / 6,152 / 59.
- **Silver:** counts and fingerprints identical to Step 6a.

The reconciliation still shows `RESULT: PASS`. `batch_902` stays in landing afterwards; like `batch_900`, it changes nothing in silver.

## Step 13. Record the results

Paste into the conversation:
- Steps 1 to 3: the outputs.
- Step 4: the listings.
- Step 5: the validate printout and the deploy output.
- Steps 6 to 12: for each one:
  - the job result
  - the `reconciliation` task output (from `Reconciliation` to `RESULT`)
  - the SQL results named in the step
- `DESCRIBE HISTORY` and the version used in Step 10.
- Any error, in full.

Then fill the test matrix in `VALIDATION_CHECKLIST.md` with what you observed.

## Step 14. Commit and push

```bash
git add reconciliation tests/unit/test_reconcile.py tests/unit/test_bundle.py databricks.yml \
        docs README.md phases/phase_06_reconciliation_resilience
git status --short
git status --short | grep -E 'output/|data/raw|\.venv|__pycache__|\.databricks/|\.env$|profiles\.yml$' || echo "no local or generated files staged"
git diff --cached | grep -nE 'dapi[0-9a-zA-Z]{16,}|DATABRICKS_TOKEN=[A-Za-z0-9]|https://[^[:space:]<]*databricks\.com' | grep -vE 'https://docs\.databricks\.com|dbc-xxxx'
git commit -m "feat(reconciliation): add legacy versus gold reconciliation task and resilience tests"
git push
```

Expected:
- **Staged:**
  - the `reconciliation/` files
  - the two test files
  - `databricks.yml`
  - `README.md`, the docs, the diagrams and the Phase 06 documents
- **Check line:** `no local or generated files staged`.
- **Secret scan:** prints nothing.
- **After the push:** the `ci` run on GitHub shows `unit-tests` with `47 passed` and no skips.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `ModuleNotFoundError: reconciliation` locally | Not run from the repository root | `cd` to the root; use `python -m` |
| Local rehearsal: `Path does not exist` | Step 2 not done, or `data/raw/ordered` missing | Step 2 |
| Task: `PATH_NOT_FOUND` under `/Volumes/.../legacy/` | Step 4 skipped or nested | Step 4 listings |
| Task: `_anomaly_manifest.json` not found | Not uploaded to `raw/retail/` | Step 4 |
| Task: `FileNotFoundError` or `PermissionError` on a `/Volumes/.../_manifest.json` path that Step 4 lists | Python file access to volumes not available on this compute (V16) | Paste the error; EXPLANATION section 10 |
| Task fails with only `SystemExit: 0` | The deployed script is the first version, which ended with `sys.exit()` | `databricks bundle deploy`, then run again |
| Task succeeds but prints nothing, and `retail_audit` has no rows | The script did not run as `__main__` (V4) | Paste the output; EXPLANATION section 10 |
| Task: `PERMISSION_DENIED` creating `retail_audit` | V8 | Run `CREATE SCHEMA workspace.retail_audit` in the SQL editor, then rerun |
| Unexplained differences in the exact comparison in Step 8 | A real difference between dbt and the legacy rules, or a wrong prediction | Paste the `UNEXPLAINED` lines and `01_latest_results.sql`; do not change expectations |
| Step 8 counts still show the anomaly rows | The removal did not take, or the full refresh did not run | The `fs ls` listing, then the full refresh again |
| Step 9 fingerprints differ from Step 6a | Different files re-delivered, or not all ingested | `fs ls` of each batch; compare row counts with `_anomaly_manifest.json` |
| `--params` or `--only` rejected | Older CLI | `databricks --version`; use "Run now with different parameters" in the job UI |
| `RESTORE` refused | V12 | Record it; Step 10's roll forward still applies |
| Quota or compute limit message | Free Edition limit (FE13) | Wait for the reset; record the message and time; continue from the same step |

## Getting back to the anomalous state

If a run stops between Steps 8 and 9, the landing folder lacks the anomaly batches. Run the Step 9 upload loop, then `databricks bundle run retail_nightly`. The pipeline picks up the batches as new files, and Step 9's expectations apply.

## Cleanup (optional, destructive)

Not needed for Phase 07, which may reuse the audit tables.
- `DROP SCHEMA workspace.retail_audit CASCADE;` removes the reconciliation results.
- `databricks fs rm -r dbfs:/Volumes/workspace/retail_landing/raw/legacy` removes the uploaded legacy outputs.
