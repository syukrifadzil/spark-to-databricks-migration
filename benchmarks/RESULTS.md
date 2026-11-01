# Benchmark and Evidence Results

Status: recorded 2026-11-01.
- **B1 to B5:** timed and recorded in `runs.csv`.
- **B6:** run and reported by the maintainer as matching the expected outcomes, but its timings are not in `runs.csv`, so no B6 time is published. Every empty cell is filled only from a recorded run, by the maintainer, following [phases/phase_07_benchmark_portfolio/MANUAL_RUNBOOK.md](../phases/phase_07_benchmark_portfolio/MANUAL_RUNBOOK.md). Method and rules: [README.md](README.md).

## 1. Environment

| Item | Value | Recorded |
|---|---|---|
| Laptop model and chip | MacBook Pro, Apple M5 | 2026-11-01 |
| CPU cores / memory | 10 / 16 GiB | 2026-11-01 |
| macOS version | 27.0.1 (26A434) | 2026-11-01 |
| Java | OpenJDK 17.0.21.0.3 (Homebrew) | 2026-11-01 |
| Python (`.venv`) | 3.15.1 | 2026-11-01 |
| PySpark | 4.3.0, `local[*]` | 2026-11-01 |
| Databricks | Free Edition, serverless compute, one workspace | 2026-11-01 |
| Databricks CLI | v1.23.0 | 2026-11-01 |
| SQL warehouse | Serverless Starter Warehouse, 2X-Small (Phase 00, FE8) | |
| Generator | seed and as-of date as committed; presets small and medium | |

## 2. Runtime

Paste the output of `python -m benchmarks.collect summary` here. Times are wall-clock seconds; the median is over the runs listed.

`python -m benchmarks.collect summary`, 2026-11-01, before B6:

| Scenario | System | Preset | Dataset | Unit | Runs | Median s | Min s | Max s |
|---|---|---|---|---|---|---|---|---|
| B1 | legacy_local | small | anomalous | total | 3 | 7.7 | 7.6 | 8.7 |
| B2 | legacy_local | medium | clean | total | 3 | 7.7 | 7.6 | 8.0 |
| B3 | databricks_job | small | anomalous | bronze_silver | 3 | 112.1 | 111.9 | 132.1 |
| B3 | databricks_job | small | anomalous | gold | 3 | 60.1 | 57.4 | 65.4 |
| B3 | databricks_job | small | anomalous | reconciliation | 3 | 71.3 | 65.3 | 107.4 |
| B3 | databricks_job | small | anomalous | total | 3 | 256.0 | 244.5 | 285.9 |
| B3 | pipeline_update | small | anomalous | running | 3 | 18.8 | 18.0 | 20.3 |
| B3 | pipeline_update | small | anomalous | total | 3 | 108.6 | 104.3 | 118.1 |
| B4 | databricks_job | small | anomalous | bronze_silver | 2 | 106.9 | 81.7 | 132.2 |
| B4 | databricks_job | small | anomalous | gold | 2 | 69.0 | 62.8 | 75.3 |
| B4 | databricks_job | small | anomalous | reconciliation | 2 | 96.8 | 94.5 | 99.1 |
| B4 | databricks_job | small | anomalous | total | 2 | 274.0 | 244.8 | 303.1 |
| B4 | pipeline_update | small | anomalous | running | 2 | 40.5 | 35.2 | 45.8 |
| B4 | pipeline_update | small | anomalous | total | 2 | 98.5 | 68.0 | 129.1 |
| B5 | pipeline_update | small | anomalous | running | 1 | 49.2 | 49.2 | 49.2 |
| B5 | pipeline_update | small | anomalous | total | 1 | 156.4 | 156.4 | 156.4 |

`databricks_job` units are the run and its tasks, from the Jobs API. `pipeline_update` units come from the pipeline event log:
- **`total`:** from the update's creation to its end.
- **`running`:** from the first `RUNNING` state to the end.

With two runs, B4's median is their average.

Notes per scenario:

| ID | Rows involved | Notes (cold start, retries, anything unusual) |
|---|---|---|
| B1 | Read per run: 558 customers, 55 products, 5,972 orders, 10,905 items, 5,934 payments, from 6, 4, 9, 6 and 10 files | The first run (8.7 s) was the slowest. Every run rereads every file |
| B2 | Read per run: 5,334 / 539 / 59,505 / 109,149 / 59,248 rows, from 4 files each | The same median as B1 with ten times the rows: JVM and Spark start-up dominate at this size |
| B3 | No new files: the pipeline reads nothing new; dbt rebuilds all three marts; reconciliation reads gold and the legacy outputs | The pipeline update processes for 18 to 20 s of its 104 to 118 s; the rest is waiting for resources and initializing. The first run's reconciliation task (107.4 s) was slower than the next two (71.3 s, 65.3 s) |
| B4 | The ten anomaly batches, 15 files, delivered after a rebuild (Phase 06 Step 9, runs 1114416582176359 and 545520166081148) | Processing rose to 35 to 46 s. The two runs' pipeline updates differ by 61 s in total, almost all of it in start-up (about 83 s against 33 s before `RUNNING`). The faster run took no longer overall than the fastest B3 run |
| B5 | Every landing file: `batch_000` to `batch_013`, `batch_900` and `batch_902` | 49.2 s processing within 156.4 s. The maintainer reported the layer counts after the refresh as expected |
| B6 | `mart_daily_sales` restored to version 6, then all three marts rebuilt | Outcomes reported as expected; timings not recorded |

How to read this table:
- **The two systems run on different hardware.** A laptop JVM and serverless cloud compute are not a like-for-like comparison, and no row says one is faster.
- **At this size, start-up time dominates.** The useful contrast is the work each run has to redo:
  - B1 and B2 reread every delivered file.
  - B3 reads no new files.
  - B4 reads only the new batches.

## 3. Cost caveats

- **No currency figures.** Databricks Free Edition has no billing, so nothing here is expressed in currency, and no price or DBU rate is applied (docs/platform_assumptions.md section 2).
- **Serverless start-up is in every workspace time.** On a paid workspace the same job could be faster or slower depending on compute settings, so these numbers do not predict production cost.
- **Usage quantities are optional.** They are recorded only if `sql/usage_probe.sql` can read the billing system table:

| Date | Job run or pipeline | SKU | Unit | Quantity |
|---|---|---|---|---|
| | | | | |

If the table is not readable, write "not available on Free Edition (B-V3)" here instead.

Recorded: no usage rows were reported for 2026-11-01, so none are published.

## 4. Data quality

From `lakeflow/validation/03_anomaly_checks.sql` and the reconciliation task. Phase 06 recorded the first two rows on 2026-11-01 (HANDOFF, Step 6d). Copy them from there, or rerun the checks.

| Check | Expected | Observed | Evidence |
|---|---|---|---|
| Anomaly checks `ok` | 18 of 18 | 18 of 18 | Phase 06 HANDOFF, Step 6d |
| Quarantined rows against the anomaly manifest | 35 of 35 | 35 of 35 | Phase 06 HANDOFF, Step 6d |
| Silver against the generator's expected state, clean feed | 0 missing, 0 unexpected | 0 and 0, as reported by the maintainer | Phase 06 HANDOFF, final runs, item 4 |
| Gold against legacy `ordered`, clean state | 0 differences on all three marts | 0 on 94 / 530 / 50 rows | Phase 06 HANDOFF, Step 8, run 755100707843223 |
| Gold against legacy `anomalous`, unexplained differences | 0 | 0, in every passing run of Phases 06 and 07 | Reconciliation output of each B3 and B4 run |

## 5. Recovery

| Scenario | Outcome expected | Outcome observed | Time (s) | Evidence |
|---|---|---|---|---|
| Pipeline full refresh from every landing file (B5), the rebuild step of R6 | Silver counts and fingerprints unchanged | Update `COMPLETED`; counts and fingerprints unchanged, as reported by the maintainer | 156.4 (49.2 processing) | Update `6413283a`, `runs.csv` |
| R7: `RESTORE` of `mart_daily_sales` (B6) | Earlier version restored | Clean headline after the restore, as reported by the maintainer | Not recorded | Phase 07 HANDOFF |
| R7: roll forward, `--only gold+` (B6) | Current gold rebuilt, reconciliation PASS | PASS and the anomalous headline, as reported by the maintainer | Not recorded | Phase 07 HANDOFF |
| R5b: ten batches delivered late (B4) | Same state as delivered on time | Reconciliation counts equal to the on-time state; layer counts and fingerprints identical (Phase 06, as reported by the maintainer) | 303.1 and 244.8 (job runs) | Runs 1114416582176359 and 545520166081148 |
