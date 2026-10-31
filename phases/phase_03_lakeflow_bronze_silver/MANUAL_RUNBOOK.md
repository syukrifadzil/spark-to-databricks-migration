# Phase 03 Manual Runbook: Lakeflow Bronze and Silver

All steps are run by the maintainer. None of these commands have been run by the author. Record the actual output of every step in `HANDOFF.md`; paste failures in full.

**Working directory and environment for every terminal step:**

```bash
cd ~/Desktop/databricks-prep/dbx-proj/spark-to-dbx
source .venv/bin/activate
```

The Databricks CLI uses the default profile `syukrifadzil` (set by `DATABRICKS_CONFIG_PROFILE` in `~/.zshrc`).

SQL steps run in the workspace **SQL Editor**:
- Use the warehouse "Serverless Starter Warehouse".
- Open the file named in the step, paste its whole content and click **Run all**.
- The files live in `lakeflow/validation/`.

**What the steps exercise:** the clean dataset is ingested first. Then the steps run a rerun with no new files, a replayed batch, the ten anomaly batches, and finally a full refresh. Each step has expected numbers. A different number is a finding: record it, and don't adjust the expectations.

## Step 0. Finish Phase 02 first

Phase 02 has a fix that has not been run, and possibly an uncommitted Phase 01. Do this before anything in the workspace.

```bash
python -m pytest -q
```

Expected: `40 passed`.
- 30 from Phase 01.
- 4 from the legacy job.
- 4 from `tests/unit/test_lakeflow_rules.py`, new in this phase.
- 2 from `tests/unit/test_dbt_project.py`, added in Phase 04.

```bash
python -m legacy_spark.retail_nightly_job --input data/raw/anomalous --output output/legacy/anomalous
python -c "import json; m=json.load(open('output/legacy/anomalous/baseline_metrics.json'))['metrics']; print(m['daily_sales.orders_placed'], m['daily_sales.orders_sold'])"
```

Expected: `5310.00 4472.00` (Phase 02 open item O1).

Then commit Phase 02 on its own:

```bash
git log --oneline -5
```

If there is no `feat(data): implement reproducible retail data generator` commit, run the Phase 01 runbook Step 10 first.

```bash
git add .gitignore legacy_spark requirements-spark.txt tests/unit/test_legacy_job.py \
        docs/data_contracts.md docs/diagrams/legacy-job.svg \
        phases/phase_01_synthetic_data phases/phase_02_legacy_spark
git status --short
git diff --cached | grep -nE 'dapi[0-9a-zA-Z]{16,}|DATABRICKS_TOKEN=[A-Za-z0-9]|https://[^[:space:]<]*databricks\.com'
git commit -m "feat(legacy): add legacy nightly PySpark job and baseline metrics"
git push
```

What to expect:
- `git status --short` shows the Phase 02 files staged (`A` or `M` in the first column).
- `lakeflow/`, `README.md`, the Phase 03 folder and the other `docs/` changes are still unstaged; they go into the Phase 03 commit (Step 13).
- The secret scan prints nothing.

## Waiting for an update

A pipeline runs one update at a time. Each step below must wait until its update has finished before uploading files or running checks. A file uploaded while an update is starting may be read by that update, which merges two steps into one and loses the evidence for the first.

Start an update and wait for it to finish:

```bash
UPDATE_ID=$(databricks pipelines start-update $PIPELINE_ID | python -c "import json, sys; print(json.load(sys.stdin)['update_id'])")
until databricks pipelines get-update $PIPELINE_ID $UPDATE_ID | grep -qE '"state": "(COMPLETED|FAILED|CANCELED)"'; do sleep 15; done
databricks pipelines get-update $PIPELINE_ID $UPDATE_ID | grep '"state"'
```

Expected: the last line shows `"state": "COMPLETED"`. For a full refresh, add `--full-refresh` after `$PIPELINE_ID` in the first line.

This loop was confirmed on the maintainer's CLI on 2026-10-31.

## Step 1. Check the workspace prerequisites

```bash
databricks current-user me
databricks schemas list workspace
databricks volumes list workspace retail_landing
```

Expected:
- Your user record.
- The schemas include `retail_landing`, `retail_bronze`, `retail_silver` and `retail_gold`.
- The volume `raw` exists.

If authentication fails, run `databricks auth login --profile syukrifadzil`.

## Step 2. Local test of the rules

This is already covered by Step 0. To run only the new tests:

```bash
python -m pytest -q tests/unit/test_lakeflow_rules.py
```

Expected: `4 passed`. Recorded on 2026-10-31: `4 passed in 6.68s`.

A failure in `test_failed_rules_match_the_validator` means the pipeline would quarantine different rows from the ones the validator flags. Paste it in full, because nothing in the workspace will reconcile until it passes.

## Step 3. Upload the pipeline code and the contract

Local test runs leave `__pycache__` folders. Remove them so they are not uploaded:

```bash
find lakeflow -name __pycache__ -type d -prune -exec rm -rf {} +
```

Then upload:

```bash
databricks workspace mkdirs /Workspace/Shared/spark-to-databricks-migration
databricks workspace import-dir lakeflow /Workspace/Shared/spark-to-databricks-migration/lakeflow --overwrite
databricks workspace import-dir data/contracts /Workspace/Shared/spark-to-databricks-migration/data/contracts --overwrite
databricks workspace list /Workspace/Shared/spark-to-databricks-migration/lakeflow
databricks workspace get-status /Workspace/Shared/spark-to-databricks-migration/lakeflow/retail_rules.py
databricks workspace get-status /Workspace/Shared/spark-to-databricks-migration/data/contracts/retail_contract.json
```

Expected:
- The import commands list the files they upload.
- The listing shows `retail_rules.py`, `pipeline.json` and the folders `transformations` and `validation`.
- Both `get-status` calls report `"object_type": "FILE"`.

This has not been verified: the CLI might import `.py` files as notebooks.
- If `get-status` on `retail_rules.py` reports `NOTEBOOK`, or the path is not found, `import retail_rules` will fail in the pipeline.
- In that case, upload the file in the UI instead: Workspace > Shared > spark-to-databricks-migration > lakeflow > kebab menu > Import > File, and choose `lakeflow/retail_rules.py`.
- Paste the `get-status` output either way.

Re-run this step whenever the pipeline code changes.

## Step 4. Upload the clean dataset to the landing volume

```bash
databricks fs cp -r data/raw/clean dbfs:/Volumes/workspace/retail_landing/raw/retail
databricks fs ls dbfs:/Volumes/workspace/retail_landing/raw/retail
databricks fs ls dbfs:/Volumes/workspace/retail_landing/raw/retail/batch_000
```

Expected:
- The first listing shows `_expected`, `_manifest.json` and `batch_000` to `batch_003`.
- `batch_000` contains the five entity CSVs.

If the files land one level deeper, in `retail/clean/...`, the CLI copied the folder rather than its contents. Fix it before going on, because the pipeline reads `retail/batch_*/`:
- Remove the volume folder with `databricks fs rm -r dbfs:/Volumes/workspace/retail_landing/raw/retail`. That deletes only the data uploaded in this step.
- Copy each item separately, for example `databricks fs cp -r data/raw/clean/batch_000 dbfs:/Volumes/workspace/retail_landing/raw/retail/batch_000`.

## Step 5. Create the pipeline

```bash
databricks pipelines create --json @lakeflow/pipeline.json
```

Expected: JSON with a `pipeline_id`. Keep it for this terminal session:

```bash
export PIPELINE_ID=<the id printed above>
databricks pipelines get $PIPELINE_ID
```

Expected in the `get` output:
- `"serverless": true`, `"catalog": "workspace"`, `"schema": "retail_silver"`
- the five configuration keys
- the `glob` library

If `create` rejects a field, paste the error and create the pipeline in the UI instead:
1. Jobs & Pipelines > Create > ETL pipeline.
2. Name `retail_bronze_silver`, catalog `workspace`, schema `retail_silver`, serverless.
3. Source code: the folder `/Workspace/Shared/spark-to-databricks-migration/lakeflow/transformations`.
4. Under Settings > Configuration, add the five keys and values from `lakeflow/pipeline.json`.

The pipeline is triggered, not continuous, so creating it starts nothing.

## Step 6. First update: clean dataset

```bash
databricks pipelines start-update $PIPELINE_ID
```

Expected: JSON with an `update_id`.

Watch the update in the UI (Jobs & Pipelines > retail_bronze_silver). Expected:
- The graph shows 25 datasets. For each entity:
  - `retail_bronze.<entity>`
  - `<entity>_valid`
  - `<entity>_typed`
  - `retail_silver.<entity>`
  - `retail_silver.<entity>_quarantine`
- The update ends **Completed**.

From the terminal: `databricks pipelines list-updates $PIPELINE_ID` shows the latest update's state.

An update that fails during initialization or graph analysis points to one of the unverified items in EXPLANATION section 4. The troubleshooting table below maps the usual errors to fallbacks. Paste the error from the event log in full.

## Step 7. Validate the clean ingestion

Run `lakeflow/validation/01_layer_counts.sql`. Expected:

| entity | bronze_rows | silver_rows | quarantine_rows |
|---|---|---|---|
| customers | 548 | 530 | 0 |
| order_items | 10,890 | 10,885 | 0 |
| orders | 5,942 | 5,300 | 0 |
| payments | 5,904 | 5,901 | 0 |
| products | 55 | 50 | 0 |

Where these numbers come from:
- Bronze equals the rows the legacy job read from the same files (Phase 02 handoff).
- Silver equals the expected final state (Phase 01).

Record the five `silver_fingerprint` values; Steps 8, 9 and 11 compare against them.

Run `lakeflow/validation/02_silver_vs_expected.sql`. Expected: `expected_rows` 530, 50, 5,300, 10,885 and 5,901. Every `missing_from_silver` and `unexpected_in_silver` must be `0`.

This one result proves that sequencing, late arrivals, replays and corrections in the clean feed were all handled as the contract defines (AC4).

Optional: the per-rule expectation counts from the event log. This query has not been verified; adjust the JSON path if the column layout differs.

```sql
SELECT timestamp, details:flow_progress.data_quality.expectations
FROM event_log('<pipeline id>')
WHERE event_type = 'flow_progress' AND details:flow_progress.data_quality IS NOT NULL
ORDER BY timestamp DESC;
```

## Step 8. Rerun with no new files

```bash
databricks pipelines start-update $PIPELINE_ID
```

When it completes, run `01_layer_counts.sql` again. Expected: every count and every fingerprint identical to Step 7 (AC5, first half).

## Step 9. Replayed batch

Upload a copy of `batch_002` under a new folder name. The source re-sending a whole day is a realistic failure:

```bash
databricks fs cp -r data/raw/clean/batch_002 dbfs:/Volumes/workspace/retail_landing/raw/retail/batch_900
databricks pipelines start-update $PIPELINE_ID
```

When it completes, run `01_layer_counts.sql`. Expected:
- **Bronze grows by the size of `batch_002`:**

  | Entity | Bronze rows |
  |---|---|
  | customers | 564 (+16) |
  | order_items | 11,096 (+206) |
  | orders | 6,263 (+321) |
  | payments | 6,013 (+109) |
  | products | 57 (+2) |

- **Silver counts and fingerprints are unchanged from Step 7** (AC5, second half).

This also tests AUTO CDC on exactly equal sequence values (EXPLANATION V3). Each replayed row has the same `(source_updated_at, event_id)` as a row already applied.

## Step 10. Anomaly batches

Upload `batch_004` to `batch_013` from the anomalous dataset into the same landing folder. The anomalous dataset is the clean dataset plus these ten batches.

```bash
for b in batch_004 batch_005 batch_006 batch_007 batch_008 batch_009 batch_010 batch_011 batch_012 batch_013; do
  databricks fs cp -r data/raw/anomalous/$b dbfs:/Volumes/workspace/retail_landing/raw/retail/$b
done
databricks fs ls dbfs:/Volumes/workspace/retail_landing/raw/retail
databricks pipelines start-update $PIPELINE_ID
```

When it completes, run `01_layer_counts.sql`. Expected:

| entity | bronze_rows | silver_rows | quarantine_rows |
|---|---|---|---|
| customers | 574 | 530 | 5 |
| order_items | 11,111 | 10,895 | 5 |
| orders | 6,293 | 5,310 | 10 |
| payments | 6,043 | 5,911 | 15 |
| products | 57 | 50 | 0 |

The silver fingerprints now differ from Step 7, which is expected. Record them for Step 11.

Run `lakeflow/validation/03_anomaly_checks.sql`. Expected: 18 rows, all with status `ok`.

For a FAIL, the check name gives the scenario. Inspect it with, for example:

```sql
SELECT * FROM workspace.retail_silver.orders_quarantine;
```

Paste the row.

Do not run `02_silver_vs_expected.sql` now. Silver legitimately differs from the clean `_expected` state after the anomalies.

## Step 11. Full refresh

```bash
databricks pipelines start-update $PIPELINE_ID --full-refresh
```

When it completes, run `01_layer_counts.sql` and `03_anomaly_checks.sql`. Expected:
- All counts and all five fingerprints are identical to Step 10.
- All checks are `ok`.

This proves that a rebuild from the landing files gives the same result as the incremental history (architecture section 5, rebuild-level idempotency).

## Step 11a. Rerun and replay evidence after the full refresh

Use this step if Steps 8 to 10 ran back to back without waiting, because their results cannot then be separated. It gives the same AC5 evidence on the final state. Wait for each update as described in "Waiting for an update".

First run `01_layer_counts.sql`, `02_silver_vs_expected.sql` and `03_anomaly_checks.sql` on the full-refresh result:
- `01` and `03`: as in Step 10.
- `02`: silver now differs from the clean `_expected` state, but only in the rows the anomalies change:

  | entity | missing_from_silver | unexpected_in_silver | Why |
  |---|---|---|---|
  | customers | 5 | 5 | schema_evolution: same values, newer `source_updated_at` and `event_id` |
  | order_items | 0 | 10 | invalid_reference: 10 new items |
  | orders | 0 | 10 | invalid_reference: 10 new orders |
  | payments | 5 | 15 | duplicate_key_conflict replaces 5; invalid_reference and payment_mismatch add 10 |
  | products | 0 | 0 | |

  Every other silver row equals the generator's expected state.

**Rerun with no new files:** start an update and wait. `01` must be identical to the full-refresh result, fingerprints included.

**Replay:**

```bash
databricks fs cp -r data/raw/clean/batch_002 dbfs:/Volumes/workspace/retail_landing/raw/retail/batch_901
```

Start an update and wait. In `01`:
- Bronze grows by 16 customers, 206 order items, 321 orders, 109 payments and 2 products: 590 / 11,317 / 6,614 / 6,152 / 59.
- Silver counts and fingerprints are unchanged.

## Step 12. Record the observations

Paste into the conversation:
- Step 3: the `get-status` output.
- Step 5: the pipeline settings as shown by `get`. Remove nothing secret; the output holds no secrets.
- Steps 6 to 11: each update's final state and duration from the UI.
- Steps 7 to 11: every query result.
- Any error, in full.

These fill `HANDOFF.md` and the FE7 row of `docs/platform_assumptions.md`.

## Step 13. Commit and push Phase 03

```bash
git add lakeflow tests/unit/test_lakeflow_rules.py phases/phase_03_lakeflow_bronze_silver \
        docs/diagrams/lakeflow-pipeline.svg docs/adr/0004-incremental-ingestion-and-quarantine.md docs/platform_assumptions.md
git status --short
git status --short | grep -E 'output/|data/raw|\.venv|__pycache__|\.pytest_cache' || echo "no generated or local files staged"
git diff --cached | grep -nE 'dapi[0-9a-zA-Z]{16,}|DATABRICKS_TOKEN=[A-Za-z0-9]|https://[^[:space:]<]*databricks\.com'
git commit -m "feat(lakeflow): add bronze and silver pipeline with contract rules and quarantine"
git push
```

Expected:
- `no generated or local files staged`.
- The secret scan prints nothing.
- The push succeeds.

`lakeflow/pipeline.json` contains workspace paths but no host name or credentials.

`README.md`, `docs/architecture.md` and `docs/diagrams/phase-plan.svg` hold changes from both Phase 03 and Phase 04, so they go into the Phase 04 commit.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `ModuleNotFoundError: retail_rules` | Module imported as a notebook, or not at `retail.code_root` (V16) | Step 3 `get-status`; upload through the UI as a file |
| `FileNotFoundError` for `retail_contract.json` | Contract not uploaded, or `open()` cannot read workspace files (V17) | Step 3; if the file is there, report it and use the fallback in EXPLANATION section 7 |
| `AttributeError` mentioning `temporary_view` | Older or different decorator name (V9) | Replace `@dp.temporary_view` with `@dp.view` in `retail_pipeline.py`, then Step 3 |
| Error naming `expect_all_or_drop` on a view | Expectations not allowed on views (V8) | EXPLANATION section 7 fallback |
| Error about publishing to `retail_bronze` | One pipeline cannot write two schemas (FE7) | EXPLANATION section 7 fallback |
| `_metadata` column cannot be resolved | File metadata column unavailable (V14) | Report it; remove the two `_metadata` columns as a stopgap |
| Update completes, bronze counts 0 | Files not at `retail/batch_*/<entity>.csv` | Step 4 listing; check `retail.landing_path` |
| Bronze counts doubled after a re-upload | Same files uploaded under a second path | Remove the extra folder, then full refresh (Step 11) |
| `02` shows differences | Rules, casts or sequencing differ from the validator | Run `SELECT * FROM e_orders EXCEPT ALL SELECT * FROM s_orders` with the CTEs to list rows; paste a few |
| `create` rejects `glob` or `schema` | Field names differ in this workspace (V15) | Create in the UI (Step 5) |
| Quota or compute limit message | Free Edition limit (FE13) | Wait for the reset; note the message and time |

## Cleanup (destructive, optional)

Not needed between phases. Phase 04 reads these silver tables.

- `databricks pipelines delete $PIPELINE_ID` deletes the pipeline. I believe this also drops the tables it publishes; check the current documentation before relying on that.
- `databricks fs rm -r dbfs:/Volumes/workspace/retail_landing/raw/retail` deletes the uploaded landing files.
