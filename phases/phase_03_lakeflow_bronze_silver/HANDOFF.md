# Phase 03 Handoff

## Status

Authored, not run. Nothing has been uploaded, created or executed. The maintainer approved Phase 03 on 2026-10-31 ("proceed") before reporting the results of the Phase 02 fix. Runbook Step 0 therefore completes Phase 02 first.

## Files created or changed

| File | Change |
|---|---|
| `lakeflow/transformations/retail_pipeline.py` | New: pipeline source, five datasets per entity |
| `lakeflow/retail_rules.py` | New: contract-derived schemas, rules and projections |
| `lakeflow/pipeline.json` | New: pipeline settings |
| `lakeflow/validation/01_layer_counts.sql`, `02_silver_vs_expected.sql`, `03_anomaly_checks.sql` | New: workspace checks |
| `tests/unit/test_lakeflow_rules.py` | New: 4 tests (rule names; rules against the validator on both samples; typed projection) |
| `docs/diagrams/lakeflow-pipeline.svg` | New |
| `docs/diagrams/phase-plan.svg` | Phase 03 in review |
| `docs/architecture.md` | API note and open questions updated with the verification results |
| `docs/adr/0004-incremental-ingestion-and-quarantine.md` | Verification section updated |
| `docs/platform_assumptions.md` | FE7 and FE14 notes |
| `README.md` | Status, phase table, layout, runbook link |
| `phases/phase_03_lakeflow_bronze_silver/*.md` | Explanation, runbook, checklist, this handoff |

## Decisions taken in this phase

- Bronze has an explicit all-string schema with rescued columns (D1). Rules are generated from the contract and mirror the Phase 01 validator (D2, D3).
- The quarantine table is separate from the silver path, and both use one rule set (D5). Silver uses AUTO CDC, SCD 1, sequenced by `(source_updated_at, event_id)` (D6).
- Pipeline code lives in `/Workspace/Shared/spark-to-databricks-migration`, uploaded with the CLI (D8). Phase 05 may replace this with a bundle.

## Outstanding assumptions

Listed with their status in `EXPLANATION.md` section 4. These are verified only in the workspace:
- V6/FE7: one pipeline publishes to two schemas.
- V8: expectations on temporary views.
- V9: the `temporary_view` decorator name.
- V10/V11: rescued columns and matching CSV columns by header name.
- V14: `_metadata` columns.
- V15: pipeline JSON fields.
- V16/V17: workspace module import and `open()`.
- V3: AUTO CDC on equal sequence values (replay test).

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| An unverified API behaves differently | Update fails at analysis | Fallbacks in EXPLANATION section 7; troubleshooting table in the runbook |
| Serverless evaluates a rule differently from local Spark | Quarantine or silver differs from the validator | Step 7 compares silver with `_expected` on real data |
| Free Edition quota stops an update | Steps delayed | Runbook troubleshooting; small dataset only |
| Landing files edited or duplicated by hand | Bronze double counts or misses changes | Landing is immutable; the runbook adds files only. A full refresh rebuilds from the files present |

## Human outputs required

- Step 0: `pytest -q` summary; anomalous `orders_placed` and `orders_sold`; Phase 02 commit hash: not yet reported.
- Step 1 (2026-10-31):
  - The CLI authenticates as the maintainer, who is in `admins`.
  - The four `retail_*` schemas exist, and the managed volume `workspace.retail_landing.raw` exists.
- Step 2: `tests/unit/test_lakeflow_rules.py`: `4 passed in 6.68s`.
- Step 3:
  - `import-dir` uploaded all six `lakeflow/` files and the contract.
  - `get-status` reports `"object_type": "FILE"` for `retail_rules.py` (3,968 bytes) and `retail_contract.json` (7,782 bytes).
  - V16 and V17 still depend on the first update.
- Step 4:
  - `databricks fs cp -r data/raw/clean/ ...` copied the folder's contents, not the folder itself.
  - The landing folder holds `_expected`, `_manifest.json` and `batch_000` to `batch_003`, and `batch_000` holds the five CSVs.
- Step 5:
  - `create` accepted `lakeflow/pipeline.json` unchanged; pipeline id `65b949fd-556c-47bd-ac1f-08855e9f7bd4`.
  - `get` shows `"effective_publishing_mode": "DEFAULT_PUBLISHING_MODE"`, serverless, catalog `workspace`, schema `retail_silver`, the five configuration keys and the `glob` library. That confirms V15 and supports V6.
- Step 6:
  - Update `77448102-eddc-4b1c-bb1b-1b94a2405ead` ended `COMPLETED` (`list-updates`). Duration not yet recorded.
  - The graph built and ran, so the pipeline code passed initialization and analysis. That means:
    - the workspace module import and `open()` of the contract worked (V16, V17)
    - `dp.temporary_view` and expectations on views were accepted (V8, V9)
    - the `_metadata` columns resolved (V14)
    - publishing to two schemas was accepted (V6/FE7)
  - Row-level behaviour is confirmed only by the Step 7 queries.
- Steps 7 to 11, as run on 2026-10-31. Updates were started back to back, and no query results were recorded:
  - Update `60c59a4f-f003-4676-98d4-b0ecbc48b095` (intended Step 8) was started. `batch_900` (Step 9) was uploaded while it was active.
  - Update `21752dea-9dd0-4100-b115-e30db660caab` (Step 9) was started. `batch_004` to `batch_013` (Step 10) were uploaded afterwards, possibly while it was still running.
  - Update `6bb80064-8c5a-4e9b-96b5-7ae8857a2ef9` (Step 10) was started, then full refresh `bf039371-798c-4c7a-8d49-922ddb523591` (Step 11).
  - Final states of these four updates: not yet reported.
  - Because files arrived during updates, Steps 8 to 10 cannot be told apart. Runbook Step 11a collects the rerun and replay evidence on the final state instead.
- Step 7 (clean-only `02` result): not captured. Step 11a's `02` result replaces it: on the final state, only the anomaly-affected rows may differ from `_expected`.
- Step 11: final states, then `01`, `02` and `03` after the full refresh:
- Step 11a:
  - A rerun with no new files was started with the wait loop and ended `"state": "COMPLETED"`; `get-update` works on this CLI.
  - `01` was not run before this rerun, so it cannot be compared with the full-refresh result. A second rerun after recording `01` gives that comparison.
  - Results: `01` before and after the second rerun, and after the `batch_901` replay:
- Step 13: commit hash after push:
- Any failures, with the full output:

## Phase 04 prerequisites

1. Phase 03 complete: every check in the runbook passes, and it is committed.
2. Silver tables populated with the anomalous state (Step 11). Phase 04 builds gold from them.
3. A way for dbt to authenticate to the SQL warehouse: an OAuth profile or a personal access token (FE11). Phase 04 documents both and stores neither in git.
4. The SQL warehouse HTTP path from the warehouse's Connection details tab, kept in the local `.env` only.
5. Explicit approval to start Phase 04.
