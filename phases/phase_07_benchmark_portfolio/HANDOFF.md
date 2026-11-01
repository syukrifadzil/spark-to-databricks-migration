# Phase 07 Handoff

## Status

In progress (2026-11-01). The maintainer approved Phase 07 on 2026-11-01 ("proceed"), after pushing Phase 06 as `df9334f`.
- **Run:** Steps 1 to 10, reported validated by the maintainer. Step 6 needed a correction.
- **Timings:** B1 to B5 are in `runs.csv`. B6 was reported as matching its expected outcomes, but its timings were not collected.
- **Committed:** `528b350`.
- **Not yet done:** the publication checklist (Step 13).

## Run log

**Step 1 (2026-11-01):** `48 passed in 31.40s`.

**Step 2:** MacBook Pro, Apple M5, 10 cores, 16 GiB (17,179,869,184 bytes); macOS 27.0.1 (26A434); OpenJDK 17.0.21.0.3; Python 3.15.1; PySpark 4.3.0; Databricks CLI v1.23.0. Copied into RESULTS.md section 1.

**Step 3, B1:** 8.7 s, 7.7 s, 7.6 s.
- Each run read 558 customers, 55 products, 5,972 orders, 10,905 items and 5,934 payments, from 6, 4, 9, 6 and 10 files.
- The first run was the slowest, as expected for a cold start.

**Step 4, B2:** `data/raw/medium` already existed (Phase 02).
- Durations: 8.0 s, 7.6 s, 7.7 s.
- Each run read 5,334 / 539 / 59,505 / 109,149 / 59,248 rows from 4 files each.
- The median equals B1's (7.7 s) with ten times the rows. This confirms the Phase 02 observation that start-up dominates at these sizes.

**Step 5, B3:** three runs, all `TERMINATED SUCCESS` with `RESULT: PASS`, and the reconciliation counts equal to Phase 06. The reference layer counts were not pasted.

| Run | Total s | bronze_silver s | gold s | reconciliation s |
|---|---|---|---|---|
| 313935765536855 | 285.9 | 112.1 | 65.4 | 107.4 |
| 716425493983975 | 244.5 | 111.9 | 60.1 | 71.3 |
| 507045070231256 | 256.0 | 132.1 | 57.4 | 65.3 |

B-V1 confirmed.

**Step 6, B4: collected wrongly at first, then corrected.**
- Run 1114416582176359 was collected correctly: 303.1 s total, bronze_silver 132.2 s, gold 75.3 s, reconciliation 94.5 s. That confirms B-V4.
- The three B3 run ids were then collected as B4 too, in place of the repeated Step 9 run. Those 12 rows were removed from `runs.csv`: B4 must contain only runs that read new files. The summary printed before the correction counted them, giving B4 four runs.
- **The repeated Step 9 run, found with `jobs list-runs`:** `545520166081148`, started 10:48:32 UTC, `SUCCESS`.
  - Collected: 244.8 s total; bronze_silver 81.7 s, gold 62.8 s, reconciliation 99.1 s.
  - Its pipeline update, `784ead26`, starts at the same second: 68.0 s total, 35.2 s running. It was recorded with `collect manual`.
- **The listing also identifies the Phase 06 Step 11 rerun (R1):** `1118333443529564`, at 10:13:09, matching update `28200eb8` at 10:13:10.
- **Start-up varies a lot.** Update `784ead26` spent about 33 s before running, against 85 to 98 s for the B3 updates. Its whole job run (244.8 s) was no longer than the fastest B3 run, despite reading ten new batches. At this size, start-up wait outweighs the data read.

**Step 7, B5:** full refresh, update `6413283a`.
- CLI: `WAITING_FOR_RESOURCES` at 11:38:08, `RUNNING` at 11:39:53, `COMPLETED` at 11:40:43.
- `pipeline_updates.sql`: 156.4 s total, 49.2 s running, `COMPLETED`, which confirms B-V2.
- Not pasted yet: the layer counts after the refresh.

**Pipeline updates, from the `pipeline_updates.sql` screenshot.** These were transcribed into `runs.csv` by the author for B3 and for B4's first run, matched to job runs by start time (within a second of each `bronze_silver` task):

| Update | First event (UTC) | Total s | Running s | Belongs to |
|---|---|---|---|---|
| 7a91d7ea | 11:19:37 | 104.3 | 18.8 | B3, run 313935765536855 |
| 5c974703 | 11:24:56 | 108.6 | 18.0 | B3, run 716425493983975 |
| af17d9eb | 11:29:28 | 118.1 | 20.3 | B3, run 507045070231256 |
| f614c52e | 05:07:25 | 129.1 | 45.8 | B4, run 1114416582176359 |
| 784ead26 | 10:48:32 | 68.0 | 35.2 | B4, run 545520166081148 (recorded by the maintainer) |
| cb79c1f5 | 10:26:05 | 164.3 | 51.1 | The repeated Phase 06 full refresh, clean state. Different data from B5, so not recorded |

What the updates show:
- **With no new files** (B3), each update spends about 18 to 20 s running and about 85 to 98 s before it, waiting for resources and initializing.
- **With ten new batches** (f614c52e), the running time rises to 45.8 s.
- **The full refresh** runs for 49.2 s.

**Step 10, first summary (2026-11-01, before B6):** 16 rows covering B1 to B5, pasted into RESULTS.md section 2. The notes table and sections 4 and 5 were filled from the run log above and the Phase 06 HANDOFF.

**Step 8, B6:** the maintainer asked how to find the roll forward's run id. It is in the first output line, `Run URL: .../runs/<run id>?o=...`, as for B3; the runbook now says so at that command.

**Remaining steps (2026-11-01), as reported by the maintainer.** "Everything has been validated and the results are as expected." No output was pasted, and `runs.csv` holds no B6 row. So the following are recorded as reported, not transcribed:
- **Layer counts after the B5 full refresh:** as expected.
  - bronze 590 / 11,317 / 6,614 / 6,152 / 59
  - silver 530 / 10,895 / 5,310 / 5,911 / 50
  - quarantine 5 / 5 / 10 / 15 / 0
  - fingerprints unchanged
- **B6:** `RESTORE` to version 6 gave the clean headline, and the `--only gold+` roll forward passed and gave the anomalous headline again. Its timings were not collected, so RESULTS.md publishes no B6 time.
- **Usage probe (optional):** not reported, so section 3 has no usage rows.

## Files created or changed

| File | Change |
|---|---|
| `benchmarks/__init__.py` | New, empty |
| `benchmarks/collect.py` | New: records legacy, job and manual measurements; prints the summary |
| `benchmarks/results/runs.csv` | New: header only |
| `benchmarks/sql/pipeline_updates.sql` | New: pipeline update durations from the event log |
| `benchmarks/sql/usage_probe.sql` | New: optional usage quantities |
| `benchmarks/README.md` | New: method, scenarios, rules, assumptions B-V1 to B-V4 |
| `benchmarks/RESULTS.md` | New: blank templates for environment, runtime, cost caveats, data quality, recovery |
| `tests/unit/test_benchmark_collect.py` | New: 1 test, no Spark needed |
| `docs/migration_narrative.md`, `docs/limitations.md`, `docs/screenshots_checklist.md`, `docs/interview_talking_points.md` | New |
| `docs/adr/0007-orchestration-as-a-bundle-job.md`, `0008-reconcile-key-by-key-against-legacy.md`, `0009-benchmark-with-measured-proxies-only.md` | New; index updated |
| `docs/architecture.md` | Status line; audit write pattern |
| `docs/case_study.md` | AC12 evidence; phase plan description |
| `docs/platform_assumptions.md` | Section 2 points to the method |
| `docs/diagrams/phase-plan.svg` | Phase 07 in review |
| `README.md` | Status, Results table, phase table, runbook link, documentation links |
| `phases/phase_06_reconciliation_resilience/HANDOFF.md` | Commit `df9334f` recorded |
| `phases/phase_07_benchmark_portfolio/*.md` | Explanation, runbook, checklist, this handoff |

## Decisions taken in this phase

- Wall-clock seconds from each system's own records; median with minimum and maximum over three runs; every run kept (EXPLANATION section 3.1, ADR 0009).
- No speed comparison between the systems, and no prices.
- The Lakehouse runs on the small preset only. The legacy job also runs on medium (section 4).
- B4 reuses the Phase 06 incremental runs instead of adding data.
- Raw run JSON stays in `output/`. Only ids, times and states reach git.

## Outstanding assumptions

B-V1 to B-V5 (EXPLANATION section 6). The most consequential:
- **B-V1:** the field names in `jobs get-run`. Every job measurement depends on them.
- **B-V2:** `event_log()` from the SQL warehouse.

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| A benchmark number is read as a speed claim | Misleading portfolio | Rules in `benchmarks/README.md`; the RESULTS.md reading notes; ADR 0009 |
| A screenshot leaks the host or an email | Workspace details public | Redaction table; check by eye before staging |
| Raw JSON committed | Host and email in git | It lives under the ignored `output/`; the Step 12 scan matches `databricks.com` URLs |
| Free Edition quota during Steps 5 to 8 | Fewer runs than planned | Record what ran; continue another day; never fill gaps by estimate |
| Version 6 no longer restorable | B6 measures a different restore | Restore the previous version and note it |
| Commit email made public | Personal address visible | Publication checklist item 3, before changing visibility |

## Human outputs required

- Step 1: `pytest -q` summary:
- Step 2: environment lines:
- Step 3: B1, three durations and collect lines:
- Step 4: B2, medium data status; three durations:
- Step 5: reference layer counts; three run ids, results and collect lines:
- Step 6: B4 collect lines, or the `get-run` error:
- Step 7: update id; `pipeline_updates.sql` row; layer counts after:
- Step 8: history rows used; `RESTORE` result and runtime; headlines; roll forward run:
- Step 9 (optional): usage rows or the error:
- Step 10: the summary table:
- Step 12: committed as `528b350` and pushed to `main` (`df9334f..528b350`, 26 files), 2026-11-01. CI result: not reported.
  - **Path check:** `no local or generated files staged`.
  - **Email check:** `no email addresses staged`.
  - **Secret scan:** it printed two lines, both false positives. They are the documentation's own mention of the `X-Databricks-Signature` parameter name: the redaction table in `docs/screenshots_checklist.md`, and the history scan command in this runbook. Neither contains a signed URL. The scan now matches `X-Databricks-Signature=`, which only a real signed URL contains.
- Follow-up commit `628e569` (`528b350..628e569`): this handoff and the corrected scan pattern.
- Step 13:
  - **Licence:** the maintainer chose "MIT and Apache 2.0" (2026-11-01). This is recorded as a dual licence, `MIT OR Apache-2.0`, at the user's option, the usual meaning of that pairing. `LICENSE-MIT` was written with the GitHub handle as copyright holder. `LICENSE-APACHE` is downloaded by the maintainer from apache.org, so it carries the canonical text.
  - **ADR 0009:** accepted by the maintainer (2026-11-01).
  - **Licence commit:** `560f286` (`628e569..560f286`, 7 files).
    - `LICENSE-APACHE` downloaded from apache.org: 202 lines, headed `Apache License` / `Version 2.0, January 2004`.
    - `LICENSE-MIT` and the README License section were committed with it.
  - **History scan output; visibility decision:**
- Any failures, with the full output:

## After Phase 07

Phase 07 is the last planned phase. Possible follow-ups, none started without approval:
1. Repeat B3 to B6 on another day to show variation.
2. A medium-preset run of the Lakehouse in a separate catalog or workspace, if quotas allow.
3. The production hardening items in `docs/case_study.md` section 7.
