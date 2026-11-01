# Phase 07 Manual Runbook: Benchmarks and Publication

All steps are run by the maintainer. None of these commands have been run by the author. Record what each step prints in `HANDOFF.md`, and the measurements in `benchmarks/results/runs.csv` (through `collect.py`) and `benchmarks/RESULTS.md`. Any expected time below is a reference from an earlier phase, not a target: record what you measure.

**Working directory and environment for every terminal step:**

```bash
cd ~/Desktop/databricks-prep/dbx-proj/spark-to-dbx
source .venv/bin/activate
set -a; source .env; set +a
mkdir -p output/benchmarks
```

`output/` is ignored by git. Raw run JSON goes there because it contains the workspace URL and your user name.

SQL steps run in the workspace SQL Editor on "Serverless Starter Warehouse", as in Phase 06.

**Starting state.** The workspace is as Phase 06 left it:
- landing holds `batch_000` to `batch_013`, `batch_900` and `batch_902`
- silver is in the anomalous state
- gold is the anomalous build

## Step 1. Unit tests

```bash
python -m pytest -q
```

Expected: `48 passed`: the 47 from Phase 06, plus `tests/unit/test_benchmark_collect.py`. That test needs neither Spark nor Java.

## Step 2. Record the environment

```bash
sw_vers
sysctl -n machdep.cpu.brand_string hw.ncpu hw.memsize
java -version
python --version
python -c "import pyspark; print(pyspark.__version__)"
databricks --version
```

Expected:
- macOS version lines and the chip name
- the core count
- memory in bytes: divide by 1,073,741,824 for GiB
- OpenJDK 17, Python 3.15, PySpark 4.3.0 and Databricks CLI v1.23.0, as recorded in Phases 02 and 05

Copy them into section 1 of `benchmarks/RESULTS.md`.

## Step 3. B1: legacy job, small anomalous, three runs

```bash
for i in 1 2 3; do
  python -m legacy_spark.retail_nightly_job --input data/raw/anomalous --output output/benchmarks/B1_$i
  python -m benchmarks.collect legacy --scenario B1 --preset small --dataset anomalous \
    --metrics output/benchmarks/B1_$i/baseline_metrics.json
done
```

Expected for each run:
- The job log ends with `done in N s`.
- The collector then prints `1 of 1 rows added to .../benchmarks/results/runs.csv` and a line `B1 legacy_local total: N s, ok`.
- **Reference only:** Phase 02 recorded 9.0 s on the small clean data.

Also note the `read ...: N rows from M files` lines of one run: they are the rows involved.

## Step 4. B2: legacy job, medium, three runs

```bash
ls data/raw/medium/_manifest.json || {
  python -m data.generators.generate --preset medium --out data/raw/medium
  python -m data.generators.validate --data data/raw/medium
}
for i in 1 2 3; do
  python -m legacy_spark.retail_nightly_job --input data/raw/medium --output output/benchmarks/B2_$i
  python -m benchmarks.collect legacy --scenario B2 --preset medium --dataset clean \
    --metrics output/benchmarks/B2_$i/baseline_metrics.json
done
```

Expected:
- **If the folder exists,** `ls` prints the manifest path. Otherwise the generator writes the medium dataset and the validator prints `PASS`.
- **Each run:** one row added.
- **Reference only:** Phase 02 recorded 9.7 s, with 59,505 orders read.

If Phase 02 kept the medium data under another folder, use that folder instead.

## Step 5. B3: Lakehouse job with no new files, three runs

Before the first run, take the layer counts as the reference for Step 7. Run `lakeflow/validation/01_layer_counts.sql` and keep the result. Expected:
- **bronze:** 590 / 11,317 / 6,614 / 6,152 / 59
- **silver:** 530 / 10,895 / 5,310 / 5,911 / 50
- **quarantine:** 5 / 5 / 10 / 15 / 0

Then, three times:

```bash
databricks bundle run retail_nightly
```

The first line is `Run URL: https://.../jobs/<job id>/runs/<run id>?o=...`. The number after `/runs/` is the run id. Do not paste the URL anywhere that gets committed. After each run:

```bash
RUN_ID=<run id>
databricks jobs get-run $RUN_ID -o json > output/benchmarks/run_$RUN_ID.json
python -m benchmarks.collect job --scenario B3 --preset small --dataset anomalous \
  --run-json output/benchmarks/run_$RUN_ID.json
```

Expected:
- **Each job run:** `TERMINATED SUCCESS` and `RESULT: PASS`.
- **Each collect:** `4 of 4 rows added`, with lines for `total`, `bronze_silver`, `gold` and `reconciliation`, all `SUCCESS`.
  - **Reference only:** Phase 06 runs took between about 2.5 and 5 minutes from the CLI timestamps.
  - Note whether the first run was slower: the warehouse or serverless compute may have been idle.

If `collect` stops with `KeyError: 'end_time'` or `'start_time'`, B-V1 is false: paste the first 40 lines of the JSON, with the URL and user name removed. Fallback: read the task durations on the run page and enter them with `collect.py manual --system databricks_job --unit <task key>`.

## Step 6. B4: incremental runs already recorded in Phase 06

These job runs read the ten anomaly batches delivered after a rebuild (Phase 06 Step 9). They are the incremental case: new files arrive, and only they are read.
- `1114416582176359`: the first Step 9.
- **The repeated Step 9:** the run that started just after the repeated full refresh. It is not one of the B3 runs, which had no new files.

To find its id, list the job's recent runs with their start times in UTC. The job id is the number after `/jobs/` in any Run URL.

```bash
databricks jobs list-runs --job-id <job id> --limit 25 -o json | python -c '
import json, sys
from datetime import datetime, timezone
data = json.load(sys.stdin)
for r in (data if isinstance(data, list) else data.get("runs", [])):
    start = datetime.fromtimestamp(r["start_time"] / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(r["run_id"], start, r.get("state", {}).get("result_state"))'
```

The repeated Step 9 run is the one whose start time matches its pipeline update in `benchmarks/sql/pipeline_updates.sql`: the first update after the repeated full refresh.

```bash
for RUN_ID in 1114416582176359 <repeated Step 9 run id>; do
  databricks jobs get-run $RUN_ID -o json > output/benchmarks/run_$RUN_ID.json
  python -m benchmarks.collect job --scenario B4 --preset small --dataset anomalous \
    --run-json output/benchmarks/run_$RUN_ID.json
done
```

Expected: `4 of 4 rows added` for each run.

If `get-run` reports that the run does not exist, B-V4 is false. Record the CLI timestamps from the Phase 06 HANDOFF in RESULTS.md instead (13:07:25 to 13:12:35 for the first Step 9), labelled "CLI timestamps". Do not enter them in `runs.csv`.

## Step 7. B5: pipeline full refresh

```bash
databricks bundle run retail_bronze_silver --full-refresh-all
```

Expected:
- The update states print with timestamps, ending in `Update ... is COMPLETED`, then `Update ID: <update id>`.
- Note the first and last timestamps as a cross-check.

Then run `benchmarks/sql/pipeline_updates.sql`. Expected:
- One row per recent update, newest first.
- The top row's `update_id` starts with the Update ID printed above, and `final_state` is `COMPLETED`.
- `total_seconds` is roughly the gap between the first and last printed timestamps.

Record it:

```bash
python -m benchmarks.collect manual --scenario B5 --preset small --dataset anomalous \
  --system pipeline_update --run-ref <update id> --started-at <first_event as 2026-11-02T01:23:45Z> \
  --seconds <total_seconds>
python -m benchmarks.collect manual --scenario B5 --preset small --dataset anomalous \
  --system pipeline_update --run-ref <update id> --started-at <first_event> \
  --unit running --seconds <running_seconds>
```

The same query also lists the updates that ran inside the B3 and B4 job runs. Each starts within a second or two of that run's `bronze_silver` task. Record them in the same way, with scenario B3 or B4. Their `running_seconds` against `total_seconds` shows how much of the pipeline task is processing and how much is start-up.

Then run `01_layer_counts.sql`. Expected: identical to the Step 5 reference, counts and fingerprints. A full refresh rebuilds from the same files.

If `event_log(...)` is refused or not found, B-V2 is false. Use the gap between the first and last timestamps the CLI printed as `--seconds`, and record that this was the source.

## Step 8. B6: gold rollback and roll forward

1. Find the clean-state version again:

   ```sql
   DESCRIBE HISTORY workspace.retail_gold.mart_daily_sales LIMIT 20;
   ```

   Version 6 is the clean build from Phase 06. Data files are kept for 7 days by default, so restoring it works until about 2026-11-08.

2. Select only the `RESTORE` line and use **Run selected**, so the runtime shown is for this statement alone:

   ```sql
   RESTORE TABLE workspace.retail_gold.mart_daily_sales TO VERSION AS OF 6;
   ```

   Expected:
   - a one-row result with the restored table size and file counts
   - the runtime under the result, for example `0.575s runtime`

   If it fails because files are missing, restore to the version just before the latest one instead, and note that.

3. Run the headline query from the Phase 06 runbook. Expected, if version 6 was restored: the clean row, 94 rows and charges 2,780,514.47.

4. Record the restore and roll forward:

   ```bash
   python -m benchmarks.collect manual --scenario B6 --preset small --dataset anomalous \
     --system sql_editor --run-ref restore_v6 --started-at <time you ran it, in UTC> --seconds <runtime>
   databricks bundle run retail_nightly --only gold+
   # The run id is in the first line of the output: Run URL: https://.../runs/<run id>?o=...
   RUN_ID=<run id>
   databricks jobs get-run $RUN_ID -o json > output/benchmarks/run_$RUN_ID.json
   python -m benchmarks.collect job --scenario B6 --preset small --dataset anomalous \
     --run-json output/benchmarks/run_$RUN_ID.json
   ```

   Expected:
   - the run is `TERMINATED SUCCESS` with `RESULT: PASS`
   - `3 of 3 rows added`: `total`, `gold` and `reconciliation`
   - the headline is the anomalous row again

## Step 9 (optional). Usage quantities

Run `benchmarks/sql/usage_probe.sql`.
- **If it returns rows:** copy the rows for the B3 to B6 run ids into section 3 of RESULTS.md. Quantities and units only.
- **If it fails with a permission or table-not-found error:** B-V3 is false. Write "not available on Free Edition (B-V3)" in section 3, with the error text.

## Step 10. Fill RESULTS.md

```bash
python -m benchmarks.collect summary
```

Expected: a markdown table with one row per scenario and unit, giving runs, median, minimum and maximum seconds. Only passed runs count.

Then fill in `benchmarks/RESULTS.md`:
- **Section 2:** paste the table, and fill the notes table (rows involved, cold starts, anything unusual).
- **Section 4:** fill from Phase 06 or rerun `lakeflow/validation/03_anomaly_checks.sql`.
- **Section 5:** fill from Steps 6 to 8.
- **The status line at the top:** change it to the date of recording.

Check that every number you enter has a source in `runs.csv`, the SQL results or a HANDOFF.

## Step 11. Screenshots

Follow `docs/screenshots_checklist.md`. Save the files to `docs/screenshots/`, and check each image against the redaction table before staging it. This step is optional for the commit, but recommended before publication.

## Step 12. Commit and push

```bash
git add benchmarks tests/unit/test_benchmark_collect.py docs README.md \
        phases/phase_07_benchmark_portfolio phases/phase_06_reconciliation_resilience/HANDOFF.md
git status --short
git status --short | grep -E 'output/|data/raw|\.venv|__pycache__|\.databricks/|\.env$|profiles\.yml$' || echo "no local or generated files staged"
git diff --cached | grep -nE 'dapi[0-9a-zA-Z]{16,}|DATABRICKS_TOKEN=[A-Za-z0-9]|X-Databricks-Signature=|https://[^[:space:]<]*databricks\.com' | grep -vE 'https://docs\.databricks\.com|dbc-xxxx'
git diff --cached | grep -niE '@gmail\.com' || echo "no email addresses staged"
git commit -m "feat(benchmarks): add benchmark harness, results and portfolio documentation"
git push
```

Expected:
- **Staged:**
  - `benchmarks/`: `__init__.py`, `collect.py`, `README.md`, `RESULTS.md`, `results/runs.csv` and `sql/`
  - the new test
  - the docs: four new documents, three ADRs, and edits to the ADR index, architecture, case study, platform assumptions and phase plan
  - `README.md`
  - the Phase 07 documents and the Phase 06 HANDOFF
  - any screenshots
- **Path check:** prints `no local or generated files staged`.
- **Secret scan:** prints nothing.
- **Email check:** prints `no email addresses staged`.
- **After the push:** the `ci` run is green, with `unit-tests` showing `48 passed`.

If either scan prints a line, do not commit. Paste the line.

## Step 13. Publication checklist

These steps make the repository public-facing. Each one is yours to decide; none is reversible in every sense once others have cloned the repository.

1. **Licence.** Choose one. The README says it is to be decided.
   - **MIT:** short and permissive.
   - **Apache-2.0:** permissive, with an explicit patent grant.
   - **No licence:** all rights reserved; others may read but not reuse.

   To add one: on GitHub, **Add file > Create new file**, name it `LICENSE`, then **Choose a license template**. Then replace the README's License section with the licence name, in a normal commit.
2. **History scan for secrets and hosts.** This scans every commit's changes, not just the current tree:

   ```bash
   git log -p --all --format= | grep -nE 'dapi[0-9a-zA-Z]{16,}|X-Databricks-Signature=|dbc-[0-9a-f]{8}-[0-9a-f]{4}' || echo "history clean"
   git log --all --name-only --format= | sort -u | grep -E '^(data/raw|output)/|(^|/)\.env$|profiles\.yml$' || echo "no ignored files in history"
   ```

   Expected: `history clean` and `no ignored files in history`. `dbt/.user.yml` from commit `6f4ff73` is known and accepted (Phase 04).
3. **Commit author email.** Commit metadata is public once the repository is public.

   ```bash
   git log --all --format='%ae' | sort -u
   ```

   - If this shows a personal address you do not want public, set the GitHub no-reply address for future commits: GitHub **Settings > Emails**, then `git config user.email <no-reply address>`.
   - Rewriting past commits is possible but changes every hash; decide before publishing, not after.
4. **Repository page.** On GitHub: the description, the website field empty, and topics such as `databricks`, `lakeflow`, `dbt`, `delta-lake`, `unity-catalog`, `pyspark` and `data-engineering`.
5. **Rendered check.** Open the README on GitHub:
   - every diagram renders
   - every link works, including `docs/` and `benchmarks/`
   - the Results table matches the Phase 06 HANDOFF
6. **Visibility.** GitHub **Settings > General > Danger Zone > Change visibility**. Do this last, after items 1 to 5.
7. **Optional tag:**

   ```bash
   git tag -a v1.0 -m "Phase 07 complete"
   git push origin v1.0
   ```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `ModuleNotFoundError: benchmarks` | Not run from the repository root | `cd` to the root; use `python -m` |
| `0 of N rows added` | That run is already in `runs.csv` | Nothing to do; a run is counted once |
| `ValueError: run ... has not finished` | `get-run` taken while the run was still active | Wait for the run to end, then fetch the JSON again |
| `KeyError` in `collect job` | B-V1: field names differ | Step 5 fallback |
| `event_log` error | B-V2 | Step 7 fallback |
| `RESTORE` fails on missing files | Version 6 older than the retention period, or vacuumed | Restore to the previous version; note it |
| Generator refuses `data/raw/medium` | Folder exists but is incomplete | Check `ls data/raw/medium`; delete it only if it is not the Phase 02 data you want to keep |
| Quota or compute limit message | FE13 | Record the message and time; continue later from the same step |
