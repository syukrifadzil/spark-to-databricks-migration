# Interview Talking Points

Short answers to the questions this project is most likely to raise, each with the file that backs it. Every number comes from a recorded run in a phase HANDOFF.

## The project in two minutes

- **The starting point:** a nightly PySpark job that reloads everything, trusts file order, counts replays twice and overwrites its reports.
- **The target:** incremental ingestion with Lakeflow into bronze and silver, explicit quality rules with quarantine, gold marts in dbt, all on Unity Catalog, deployed as one bundle job.
- **The proof:** on correctly ordered data, gold matches the legacy output exactly on every key. On anomalous data, every difference traces to a documented cause. Both checks run as the job's last task. `docs/migration_narrative.md`.

## Design questions

**Why Lakeflow for bronze and silver, but dbt for gold?**
- **Different jobs.** Ingestion needs file tracking, schema rescue, expectations and change-data-capture. Lakeflow provides those declaratively.
- **Gold is business logic.** It reads best as tested, documented SQL with lineage, which is dbt's strength.
- **One writer per schema** avoids two tools owning the same table. ADR 0001.

**How do late and replayed records work?**
- AUTO CDC sequences silver by `source_updated_at` and `event_id`. An older version arriving late never overwrites a newer one, and an identical replay changes nothing.
- The legacy job gets both wrong, by design, and those are the differences the reconciliation explains. `docs/data_contracts.md`, ADR 0004.

**Why quarantine instead of dropping bad rows?**
- Dropping hides the problem.
- Each failed row is kept with the rule it broke, so quarantine counts can be checked against the anomaly manifest. The run recorded 35 of 35.

**Why compare key by key and not just totals?**
- Totals can cancel out.
- Per-key row hashes show exactly which rows differ. A difference is explained only when a manifest cause touches that key. ADR 0008.

**Why is the exact match against "ordered" data and not the clean feed?**
- On the clean feed, the legacy job is wrong by design: late arrivals and replays.
- An exact match there would mean copying its bugs. The ordered dataset has the same final state with no late deliveries, so the legacy rules give the right answer on it.

## Operations questions

**What happens when reconciliation fails?**
- The task raises an error and the job run fails.
- This was tested deliberately: with the wrong dataset parameter, it failed on exactly the 2 dates and 5 customers the anomaly scenarios change.

**How do you recover from a bad batch?**
- Remove the batch from landing and run a pipeline full refresh. Silver came back equal to the generator's expected state.
- For gold: Delta `RESTORE` to an earlier version, then rebuild forward with `dbt build`.

**How is it deployed?**
- A Declarative Automation Bundle defines the pipeline and the three-task job. The maintainer deploys from a terminal.
- CI runs the unit tests (including local Spark), `dbt parse` with a placeholder profile and a token scan, with no workspace credentials. ADR 0005, ADR 0007.

## What went wrong

Good material for "tell me about a problem you solved". The full table is in `docs/migration_narrative.md` section 5.
- **Spark skips `_manifest.json`.** Names starting with `_` count as hidden, even when the path is given explicitly. The fix was to read with `open()`, plus an end-to-end test that would have caught it.
- **`SystemExit: 0` failed the task.** A serverless Python task reported it as a failure. Now the script ends normally, and signals failure by raising.
- **The platform ran a failed task twice under the same run id.** The audit rows were duplicated. The fix was a delete-then-append per run id, verified by repeating the failing run.
- **The streaming tables refused time travel.** A missed silver measurement could not be recovered, so two steps were rerun. Lesson: capture state evidence while the state exists.

## Honest limits

Say these before being asked. `docs/limitations.md`.
- Free Edition, synthetic data, small preset, one seed.
- No speed comparison between a laptop and serverless compute, and no cost in currency.
- Cause-based explanation can hide a defect on a touched key. The exact comparison is the guard.

## Numbers worth remembering

| Fact | Value | Source |
|---|---|---|
| Gold against legacy `ordered`, clean state | 94 / 530 / 50 rows, 0 differences | Phase 06 HANDOFF, Step 8 |
| Unexplained differences, anomalous state | 0 | Phase 06 HANDOFF, Steps 6c and 9 |
| Quarantined rows against the manifest | 35 of 35 | Phase 06 HANDOFF, Step 6d |
| Unit tests | 47 passed locally in Phase 06; Phase 07 adds one | Phase 06 HANDOFF |
| Legacy job, small and medium preset | 9.0 s and 9.7 s, start-up dominated | Phase 02 HANDOFF |
| Lakehouse job runtimes | See `benchmarks/RESULTS.md` | Phase 07 |
