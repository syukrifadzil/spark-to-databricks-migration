# Phase 07 Explanation: Benchmark and Portfolio

Status: written, not yet run. The harness and its test have not been executed. Every expected value in the runbook is a reference from an earlier phase's recorded run, never a prediction of a benchmark result. The benchmark results are blank until the maintainer records them.

## 1. Objectives

1. **A reproducible benchmark harness.** It records wall-clock runtimes of the legacy job and the Lakehouse from each system's own records, with the environment stated (AC12).
2. **Blank results templates** for runtime, cost caveats, data quality and recovery. They are filled only from recorded runs.
3. **Portfolio material** for a public reader:
   - the README
   - a migration narrative
   - decision records for the decisions of Phases 05 to 07
   - a limitations page
   - a screenshots checklist with redaction rules
   - interview talking points
4. **A manual publication checklist:** licence, history scan, author email, visibility.
5. **Nothing overstated.** Free Edition is not presented as production, the two systems are not compared on speed, and no cost appears in currency.

## 2. Data flow of a measurement

```
legacy job ── baseline_metrics.json (duration_seconds) ──┐
job run ───── databricks jobs get-run -o json ───────────┤
pipeline ──── event_log() via sql/pipeline_updates.sql ──┼─> collect.py ─> results/runs.csv ─> collect.py summary ─> RESULTS.md
SQL editor ── runtime shown under the result ────────────┘        (manual)
```

1. **Each system already records its own timing.**
   - The legacy job writes `duration_seconds` to `baseline_metrics.json` (Phase 02).
   - The Jobs API returns `start_time` and `end_time` for the run and for each task.
   - The pipeline event log timestamps every state change of an update.
   - The SQL editor shows each statement's runtime.
2. **`collect.py` turns those records into rows** of one CSV file. It never starts a run.
3. **`collect.py summary` reduces the rows** to a median, minimum and maximum per scenario and unit. The maintainer pastes that table into `RESULTS.md`.

## 3. The harness, file by file

### 3.1 `benchmarks/collect.py`

Four subcommands, standard library only:

| Subcommand | Input | Rows written |
|---|---|---|
| `legacy` | `baseline_metrics.json` | One `total` row: `run_ref` and `started_at_utc` are the job's own `started_at_utc` |
| `job` | `databricks jobs get-run <id> -o json` saved to a file | One `total` row for the run, and one per task that has start and end times |
| `manual` | Values typed on the command line | One row, for pipeline updates and SQL statements |
| `summary` | `results/runs.csv` | Prints a markdown table; writes nothing |

**Row format.** Each row is `scenario, system, preset, dataset, run_ref, started_at_utc, unit, seconds, result`, one per run and unit.
- **Why one row per unit:** a job run has a total and three tasks. A wide format would need a column per task, and different tasks per scenario. The long format takes any unit, and the summary groups on it.
- **Alternative:** a JSON file per run. It is harder to read in a diff, and CSV opens in any spreadsheet.

**Privacy filter.** The `get-run` JSON contains `run_page_url`, with the workspace host and id, and `creator_user_name`, the maintainer's email. `job_rows` copies only the run id, task keys, times and result states.
- The raw JSON stays under `output/benchmarks/`, which git ignores.
- The unit test puts a URL and an email address in the input and asserts that neither reaches the CSV.

**No double counting.** `append` skips a row whose scenario, run and unit are already in the file. Collecting the same run twice would otherwise give it two votes in the median. The alternative, overwriting the file each time, would lose earlier runs.

**Skipped tasks.** A task that never started, such as one skipped after a failure, has no times, so `job_rows` leaves it out instead of recording a zero or a negative duration. A run still in progress has no `end_time`, and `job_rows` refuses it with a clear error.

**Summary statistics.**
- **Median, not mean.** One cold start after an idle period can be several times slower than the others. A mean would let that one run move the result; a median of three does not.
- **Minimum and maximum are shown,** so the spread, cold start included, stays visible. No run is dropped.
- **Only passed runs count:** `ok` for the legacy job and manual entries, `SUCCESS` for job runs.

**Why a script and not a notebook or a timing wrapper:**
- **`time` around each command:** it measures the CLI's waiting and polling, and it gives no per-task breakdown. Phase 02 also found that `time` does not see the JVM's CPU work.
- **A notebook in the workspace:** it would not cover the legacy job, and it would add an execution path that CI cannot test.
- **The chosen script:** it runs locally, needs no dependency, and has a unit test that CI runs on every push.

### 3.2 `benchmarks/sql/pipeline_updates.sql`

This query reads the pipeline's event log with the `event_log()` table function and groups the events by `origin.update_id`:
- **`total_seconds`:** from the first event of the update (its creation) to the last. It includes the wait for serverless resources.
- **`running_seconds`:** from the first `RUNNING` state to the end. This is the processing part.
- **`final_state`:** the last `update_progress` state, so a failed update is visible.

Splitting the two durations matters on serverless. According to the CLI timestamps, Phase 06's full refresh spent about 95 of its 138 seconds before `RUNNING`: `WAITING_FOR_RESOURCES` at 04:44:40, `RUNNING` at 04:46:16 and `COMPLETED` at 04:46:58. That is a reading of those printed timestamps, not a measurement taken with this query.

**Alternative:** `databricks pipelines get-update`. Its JSON has the update's creation time but, as far as the recorded outputs show, no end time. The CLI's printed timestamps are the fallback (B-V2).

**Rows written are not computed.** The event log has per-flow output metrics, but how they add up across micro-batches and AUTO CDC flows has not been verified here. The layer counts are an exact, already verified source for rows, so the results use those.

### 3.3 `benchmarks/sql/usage_probe.sql` (optional)

This query reads usage quantities per job run and pipeline from `system.billing.usage`. It is only a probe: whether Free Edition exposes this table is unknown (B-V3). If it does, quantities and units are recorded. No price is applied, because there is no bill to apply it to, and published list prices would turn a measurement into an estimate.

### 3.4 `benchmarks/results/runs.csv` and `benchmarks/RESULTS.md`

`runs.csv` holds only its header. `RESULTS.md` has five sections, matching the brief:
- **Environment:** machine and versions, filled in Step 2.
- **Runtime:** the summary table and per-scenario notes.
- **Cost caveats:** fixed statements, plus the optional usage table.
- **Data quality:** the checks with expected values. The observed column is filled from Phase 06 or a rerun of the checks.
- **Recovery:** the outcome and time of each recovery action.

Every observed cell is empty. The expected column in the data quality and recovery tables states what the earlier phases' rules require, not a result.

### 3.5 `tests/unit/test_benchmark_collect.py`

One test, covering the logic that can go wrong silently:
- task and total durations from millisecond timestamps
- the epoch conversion of the start time
- a skipped task left out
- a second `append` of the same run adding nothing
- no URL or email address in the output file
- the summary row

It needs no Spark, so it also runs where Java is missing. The local test total becomes 48.

## 4. The scenarios

| ID | Measures | Why it is included | Alternative not taken |
|---|---|---|---|
| B1 | Legacy full reload, small anomalous | The nightly cost of the old system on the same input the Lakehouse holds | Clean data only: the workspace holds the anomalous feed |
| B2 | Legacy full reload, medium | How a full reload behaves with ten times the rows | Medium in the workspace: see below |
| B3 | Job with no new files | The steady-state nightly cost of the new system, three runs | One run: a cold start would distort it |
| B4 | Job after ten late batches | The incremental case: only new files are read | Upload more replays: adds bronze rows for no new information |
| B5 | Pipeline full refresh | The cost of the recovery path (R6) | Timing it inside the job: the job cannot run a full refresh |
| B6 | `RESTORE` plus `--only gold+` | The cost of a gold rollback and roll forward (R7) | A dbt rebuild only: omits the cheaper restore path |

**Why the Lakehouse runs on the small preset only.** Running medium in the workspace would mean:
- replacing the landing data
- regenerating and re-uploading the legacy outputs for reconciliation
- leaving the Phase 06 state behind

All of that on a platform with undocumented quotas (FE13). The legacy job runs on medium locally because it costs seconds and touches nothing else. The consequence is stated in RESULTS.md: the medium row describes the legacy job only.

**Why B4 reuses Phase 06 runs.** Those runs read exactly the ten anomaly batches after the rebuild. That is a real incremental delivery, already reconciled. Collecting them costs one `get-run` each, provided the job still holds their history (B-V4).

**Why no speed comparison.**
- The legacy job runs on a laptop and the Lakehouse on shared serverless compute. Any ratio between them measures the hardware as much as the design.
- At the small preset, start-up dominates both:
  - Phase 02 measured 9.0 s on small and 9.7 s on medium, ten times the rows.
  - From its printed timestamps, the Phase 06 full refresh spent about 95 of 138 seconds before its flows started running.
- What the results can show honestly is the difference in work:
  - **Legacy:** rereads every file every night (B1, B2).
  - **Lakehouse:** reads nothing new on a quiet night (B3) and only the new files on a busy one (B4).
  - **Recovery:** has explicit, measurable paths (B5, B6).

## 5. Portfolio documents

| File | Purpose | Sources |
|---|---|---|
| `README.md` | Entry point: status, a Results table, documentation links | Phase 06 HANDOFF for every number |
| `docs/migration_narrative.md` | The story, phase by phase: decisions, evidence, what went wrong | Phase HANDOFFs 02 to 06 |
| `docs/limitations.md` | What the project does not show, and where evidence is weaker | Case study, platform assumptions, HANDOFF status lines |
| `docs/screenshots_checklist.md` | Ten screenshots, with redaction rules | The redaction rules come from what earlier screenshots exposed: host, workspace id, email in tabs and in `DESCRIBE HISTORY` |
| `docs/interview_talking_points.md` | Short answers with pointers to evidence | ADRs, narrative, HANDOFFs |
| `docs/adr/0007` to `0009` | Decisions from Phases 05 to 07 that had no record yet | Phase 05 and 06 EXPLANATIONs |

Two choices about these documents:
- **Separate documents, not one long README.** A reviewer reads the README first and may stop there, so it carries the results table and links. The narrative and the talking points serve different readers: a hiring manager, and the maintainer preparing for interviews. Keeping them separate keeps each one short.
- **Reported evidence is marked.** Several phases have results the maintainer reported as matching rather than pasted in full. The narrative and the limitations page say so, rather than presenting every result as transcribed. That keeps G8 ("every published result is backed by a recorded run") honest about what kind of record backs it.

**ADR status.** 0007 and 0008 are `Accepted`, because those decisions were executed and verified in Phases 05 and 06. 0009 is `Proposed` until the maintainer reviews this phase.

**Other edits:**
- `docs/architecture.md`: the status line (built and verified, not "proposed"), and the audit write pattern (replace per run id, since Phase 06).
- `docs/case_study.md`: AC12's evidence names the results files, and the phase plan image description is current.
- `docs/platform_assumptions.md` section 2: points to the method.
- `phase-plan.svg`: Phase 07 in review.

## 6. Assumptions

| ID | Assumption | Status | Checked by |
|---|---|---|---|
| B-V1 | `jobs get-run -o json` returns `start_time`, `end_time` (milliseconds) and `state.result_state` for the run and each task | Confirmed (2026-11-01): every B3 collect added 4 rows with `SUCCESS` | Runbook Step 5 |
| B-V2 | `event_log('<pipeline id>')` is queryable from the SQL warehouse by the pipeline owner, and `details` takes the `:` path | Confirmed (2026-11-01): `pipeline_updates.sql` returned 10 updates, all `COMPLETED` | Step 7 |
| B-V3 | `system.billing.usage` is readable on Free Edition | Unknown | Step 9 |
| B-V4 | Job run history still holds the Phase 06 runs | Confirmed (2026-11-01): run 1114416582176359 was fetched | Step 6 |
| B-V5 | Version 6 of `mart_daily_sales` can still be restored | Holds within the default 7-day file retention unless the files were vacuumed | Step 8 |

## 7. Failure modes

| Symptom | Cause | Response |
|---|---|---|
| `KeyError` in `collect job` | B-V1 false: different field names | Paste a redacted JSON excerpt; enter task times by hand with `manual` |
| `event_log` refused | B-V2 false | Use the CLI's printed timestamps; label the source |
| A B3 run much slower than the others | Cold start | Keep it; the median and the min/max show it |
| A run fails | A real problem, or a quota | It does not count in the summary. Record it in the notes, and do not rerun until there are three passing runs without saying so |
| `RESTORE` refused for version 6 | Files outside retention | Restore the previous version instead and note it |

## 8. Limitations of this phase

- Three runs per scenario show the spread but do not support statistical claims.
- Benchmarks run on one day, one workspace and one laptop. Repeating them another day may give different times, which is why the environment and date are recorded with them.
- The harness measures wall-clock only. CPU, memory and I/O are not observable on serverless, and only partly locally.
- The publication checklist cannot be verified by the author. Licence, visibility and author email are the maintainer's decisions.
