# Phase 05 Handoff

## Status

Complete (2026-11-01).
- **Workspace:** the maintainer ran and verified every step. The bundle was validated, the pipeline bound, the bundle deployed, and the job run to success with data unchanged.
- **Code:** committed as `91fc614`.
- **CI:** all three jobs passed on a pull request. The maintainer approved Phase 05 on 2026-11-01 ("Proceed").

## Files created or changed

| File | Change |
|---|---|
| `databricks.yml` | New: bundle with the pipeline (bound, `prevent_destroy`), job `retail_nightly`, `dev` target |
| `.github/workflows/ci.yml` | New: `unit-tests`, `dbt-parse`, `secret-scan` |
| `tests/unit/test_bundle.py` | New: job dbt versions equal `requirements-dbt.txt` |
| `lakeflow/transformations/retail_pipeline.py` | Docstring: settings come from `databricks.yml` |
| `docs/diagrams/delivery.svg` | New |
| `docs/diagrams/phase-plan.svg` | Phase 05 in review |
| `docs/architecture.md` | Sections 8, 9 and 13 updated for the bundle and job |
| `docs/adr/0005-human-operated-execution-and-ci-scope.md` | Verification section: what CI checks |
| `README.md` | Status, phase table, layout, runbook link |
| `phases/phase_05_orchestration_cicd/*.md` | Explanation, runbook, checklist, this handoff |

## Decisions taken in this phase

- Bind the Phase 03 pipeline to the bundle instead of creating a new one; `prevent_destroy` on it (EXPLANATION D2).
- Pipeline code is synced by the bundle; `/Workspace/Shared` is no longer used after deployment (D3).
- The dbt task uses `warehouse_id`, so Databricks supplies the connection; no profile or token in git (D4).
- Two tasks, one run at a time, no schedule (D5). One `dev` target in development mode (D7).
- CI has no secrets and does not deploy (D9, D11). No linter until its rules are chosen (D10).

## Assumptions

Confirmed (EXPLANATION section 4):
- by the 2026-11-01 workspace run: V3, V4, V9, V13, V14, V17
- by the pull request CI run: V16
- Free Edition: FE9, FE10, FE12 and FE14 (`docs/platform_assumptions.md`)

None of the Phase 05 assumptions remain open.

## Observations from the run

- `bind` planned `edition: null -> "ADVANCED"`, because the bundle sets an edition where the Phase 03 pipeline had none. The update in the job succeeded with it. No other effect was observed.
- The pipeline is now in development mode (`development: True`) and is named `[dev syuk_fadzil] retail_bronze_silver`, as D7 intends.
- The bundle uploaded 183 files: the whole committed tree, including `docs/` and `phases/` (D1).
- `bundle run` prints only an `artifacts_link` for the dbt task. That link is a time-limited signed download URL. It must not be committed or shared. The dbt log is read on the run page instead (runbook Step 6).
- Step 9 removed `/Workspace/Shared/spark-to-databricks-migration`. Rollback step 2 therefore needs the Phase 03 upload repeated first.

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Deploy before bind | A second pipeline claims the same tables | Runbook order; troubleshooting row; `summary` checks the id |
| Bundle changes the pipeline's code path | Update fails to find the code or contract | Step 3 prints the resolved paths before anything changes; rollback section |
| dbt task unavailable or cannot install dbt | Gold not built by the job | Fallbacks F2 and F3; local `dbt build` still works |
| CI action versions unavailable | CI red for reasons unrelated to the code | Lower the major version |
| `bundle destroy` run by mistake | Pipeline and tables could be deleted | `prevent_destroy`; runbook warning |
| Rollback after Step 9 | `/Workspace/Shared` no longer holds the Phase 03 code | Repeat the Phase 03 upload step before rollback step 2 |

## Human outputs required

- Step 0: reported done. `main` was at `fbc624b` before the Phase 05 push.
- Step 1: `Databricks CLI v1.23.0`. `bind` worked in Step 4b.
- Step 2: `41 passed in 14.43s`.
- Step 3: `Validation OK!`, target `dev`, path `/Workspace/Users/<maintainer>/.bundle/spark_to_databricks_migration/dev`. Resolved settings:
  - pipeline `[dev syuk_fadzil] retail_bronze_silver`
  - glob, `retail.code_root` and `retail.contract_path` under `.../dev/files/`
  - landing path `/Volumes/workspace/retail_landing/raw/retail`
  - tasks `['bronze_silver', 'gold']`
  - `dbt_task` with `warehouse_id` resolved to an id, catalog `workspace`, schema `retail_gold`, and `project_directory` `.../dev/files/dbt`
- Step 4a: last update `COMPLETED`. Counts before: reported identical to Step 7, not pasted.
- Step 4b: the plan listed the code paths, `deployment`, `edition`, the name and the `dev` tag. Result: `Successfully bound pipeline with an id '65b949fd-556c-47bd-ac1f-08855e9f7bd4'`.
- Step 5: deploy:
  - `Updated pipelines.retail_bronze_silver`, `Created jobs.retail_nightly`
  - `Files: 183 uploaded, 0 deleted`, `Resources: 1 created, 1 changed, 0 deleted, 0 unchanged`
  - `summary` lists both resources, and the pipeline id is unchanged
  - `pipelines get`: the prefixed name, `development: True`, and the glob and code root under `.../dev/files/`
  - Listing:
    - no `.env`, `output`, `.venv*` or `data/raw`
    - `dbt/` has no `profiles.yml`, `target` or `logs`
- Step 6: `TERMINATED SUCCESS`, run time about 3 min 33 s (from the CLI timestamps, 01:32:52 to 01:36:25 local time). The dbt summary line from the `gold` task was not pasted. The task succeeding means `dbt build` exited without errors.
- Step 7: after the run:

  | entity | bronze | silver | quarantine |
  |---|---|---|---|
  | customers | 574 | 530 | 5 |
  | order_items | 11111 | 10895 | 5 |
  | orders | 6293 | 5310 | 10 |
  | payments | 6043 | 5911 | 15 |
  | products | 57 | 50 | 0 |

  - Fingerprints were shown and reported unchanged.
  - Gold checks: 12 of 12 `ok`.
  - Headline from `mart_daily_sales`: 96 rows, 4478 orders sold, gross 2646546.91, charges 2780589.47, refunds 146764.64, net 2633824.83.
- Step 8: FE9, FE10, FE12 and FE14 confirmed (see `docs/platform_assumptions.md`). No quota message.
- Step 9: `workspace delete --recursive` run on the Phase 03 upload; it printed nothing.
- Step 10: `91fc614` (`fbc624b..91fc614`, 14 files). Staged-files check printed `no local or generated files staged`. Secret scan printed nothing.
- Step 11: pull request from `ci-check` (commit `ceb51df`): "All checks have passed".
  - `ci / dbt-parse (pull_request)`: successful in 40s
  - `ci / secret-scan (pull_request)`: successful in 5s
  - `ci / unit-tests (pull_request)`: successful in 1m
  - `unit-tests` log: `41 passed in 41.35s`, with no `SKIPPED` lines, so the Spark tests ran with Java.
  - Workflow runs: `ci #1`, the push of `91fc614` to `main`, green in 1m 46s; `ci #2`, pull request #1, green in 1m 33s.
  - The pull request run shows one annotation notice; its text was not reported.
- Any failures, with the full output: none in the workspace steps. Two operator slips had no effect: a mistyped `atabricks`, and `BUNDLE_FILES` first set to the landing volume. The runbook now spells out that path.

## Phase 06 prerequisites

1. Phase 05 committed and CI green. The job has run end to end (2026-11-01).
2. The legacy outputs from Phase 02 (`output/legacy/clean` and `output/legacy/anomalous`) still on disk, or regenerated with the Phase 02 runbook.
3. Decide where reconciliation runs. The options are local Python reading gold through the SQL warehouse, or a job task in the workspace. Phase 06 compares them; the job task depends on the Step 8 findings.
4. Explicit approval to start Phase 06.
