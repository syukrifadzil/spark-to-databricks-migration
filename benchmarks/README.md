# Benchmarks

How long the legacy job and the Lakehouse take for the same work, measured on the maintainer's laptop and on Databricks Free Edition. Every number in [RESULTS.md](RESULTS.md) comes from a recorded run. Nothing here is estimated, and nothing is published before it is recorded.

## What is measured

| Measure | Source | Collected with |
|---|---|---|
| Legacy job wall-clock | `duration_seconds` that the job writes to `baseline_metrics.json`, from session start to the last write | `collect.py legacy` |
| Job run and task wall-clock | `start_time` and `end_time` of the run and of each task, from `databricks jobs get-run` | `collect.py job` |
| Pipeline update wall-clock | First and last event of the update in the pipeline event log, total and from `RUNNING` | `sql/pipeline_updates.sql`, then `collect.py manual` |
| SQL statement time | The runtime the SQL editor shows under the result | `collect.py manual` |
| Rows | The layer counts (`lakeflow/validation/01_layer_counts.sql`) and the legacy job's read log | Copied into RESULTS.md |
| Usage quantity (optional) | `system.billing.usage`, if Free Edition exposes it | `sql/usage_probe.sql` |

All times are wall-clock seconds. CPU time is not measured: Phase 02 found that `time` does not see the JVM's work, and serverless compute exposes no CPU figure.

## Scenarios

| ID | System | What runs | Data | Runs |
|---|---|---|---|---|
| B1 | Legacy, local | Full reload of every batch, three marts written | small, anomalous | 3 |
| B2 | Legacy, local | The same, ten times the rows | medium, clean | 3 |
| B3 | Databricks job | `retail_nightly` with no new files: pipeline update, `dbt build`, reconciliation | small, anomalous | 3 |
| B4 | Databricks job | `retail_nightly` after ten batches arrive late (Phase 06 Step 9) | small, anomalous | Runs already recorded |
| B5 | Pipeline | Full refresh of bronze and silver from every landing file | small, anomalous | 1 |
| B6 | Gold | `RESTORE` of one mart, then `retail_nightly --only gold+` | small, anomalous | 1 |

Why these:
- **B1 and B3** are the nightly run of each system on the same input.
- **B2** shows how the legacy full reload behaves with ten times the data. The Lakehouse is not run on medium, because that would mean replacing the landing data and the Phase 06 state, and Free Edition quotas are unknown (FE13).
- **B4** is the incremental case, where new files arrive. It reuses the Phase 06 runs instead of adding data again.
- **B5 and B6** are the recovery costs: rebuilding silver, and rolling gold back and forward.

## Rules

1. Record every run, including the slow first run after the workspace has been idle. Report the median with the minimum and maximum, never a hand-picked best run.
2. Record the environment with the results: machine, Java, Python and Spark versions for the legacy job; Free Edition, serverless and the date for the workspace.
3. Never compare the two systems as faster or slower. They run on different hardware. At this size, start-up dominates both: JVM and Spark start-up locally (Phase 02 measured 9.0 s on small and 9.7 s on medium), and serverless start-up in the workspace. The comparison that matters is what each system has to redo: the legacy job rereads everything every night, while the pipeline reads only new files.
4. No prices. Free Edition has no billing; usage quantities, if readable, are recorded as quantities.
5. Raw run JSON goes under `output/benchmarks/`, which git ignores. It contains the workspace URL and the user's name, and `collect.py` keeps only ids, times and states.

## Files

| File | Purpose |
|---|---|
| `collect.py` | Appends measured rows to `results/runs.csv` (skips a run already recorded) and prints the summary table |
| `results/runs.csv` | Every measured row, one per run and unit (`total` or a task key) |
| `sql/pipeline_updates.sql` | Duration of the latest pipeline updates from the event log |
| `sql/usage_probe.sql` | Optional usage quantities from the billing system table |
| `RESULTS.md` | Templates for runtime, cost caveats, data quality and recovery, filled from recorded runs |

The procedure is in [phases/phase_07_benchmark_portfolio/MANUAL_RUNBOOK.md](../phases/phase_07_benchmark_portfolio/MANUAL_RUNBOOK.md).

## Assumptions to verify

| ID | Assumption | Checked by | Fallback |
|---|---|---|---|
| B-V1 | `databricks jobs get-run <id> -o json` returns `start_time`, `end_time` and `state.result_state` for the run and for each task, in milliseconds | Runbook Step 5 | Task durations from the run page, entered with `collect.py manual` |
| B-V2 | `event_log('<pipeline id>')` can be queried from the SQL warehouse by the pipeline's owner, and `details` takes the `:` JSON path | Runbook Step 7 | The timestamps that `bundle run retail_bronze_silver` prints for each update state |
| B-V3 | `system.billing.usage` is readable on Free Edition | Runbook Step 9 (optional) | State that usage could not be measured |
| B-V4 | The job keeps run history long enough to fetch the Phase 06 runs | Runbook Step 6 | Use the CLI timestamps recorded in the Phase 06 HANDOFF, labelled as such |
