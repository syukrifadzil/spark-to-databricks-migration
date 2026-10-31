# Phase 04 Handoff

## Status

Complete. Run by the maintainer on 2026-10-31 and 2026-11-01. The install, connection and docs results are recorded below. On 2026-11-01 the maintainer reported that every runbook check was correct, including the Phase 02 and 03 checks from Step 0. The `dbt build` summary and the Step 6 to 8 and 10 query results were not pasted into the conversation, so their lines below say only that they were reported verified. Committed together with Phases 02 and 03.

## Files created or changed

| File | Change |
|---|---|
| `dbt/dbt_project.yml`, `dbt/profiles.example.yml` | New |
| `dbt/macros/business_date.sql` | New |
| `dbt/models/staging/_sources.yml`, `_staging.yml`, `stg_*.sql` (5) | New |
| `dbt/models/intermediate/int_order_balances.sql` | New, ephemeral |
| `dbt/models/marts/_marts.yml`, `mart_*.sql` (3) | New |
| `dbt/tests/business/*.sql` (8) | New, one per contract business rule |
| `dbt/checks/04_gold_checks.sql` | New, SQL editor checks |
| `requirements-dbt.txt` | New, pinned to dbt-core 1.12.6 and dbt-databricks 1.13.0 |
| `tests/unit/test_dbt_project.py` | New, 2 static tests |
| `docs/diagrams/dbt-gold.svg` | New |
| `docs/diagrams/phase-plan.svg` | Phase 04 in review |
| `docs/architecture.md` | Section 4: no `generate_schema_name` override needed |
| `README.md` | Status, phase table, layout, runbook link |
| `phases/phase_04_dbt_gold/*.md` | Explanation, runbook, checklist, this handoff |

## Decisions taken in this phase

- Staging views and mart tables both live in `retail_gold`, with no custom schemas (EXPLANATION D1).
- Severity rule: error for pipeline or model defects, warn for source data problems, which covers relationships and business rules (section 3.5).
- Business date from a fixed UTC+8 offset on epoch seconds (D4).
- dbt gets its own Python 3.12 environment; OAuth is the default target and a token target is the fallback (section 5).

## Outstanding assumptions

- dbt 1.10.5 or later installs on Python 3.12 with the Databricks adapter.
- OAuth user-to-machine works for dbt on Free Edition (FE11). If not, the token target is used.
- `catalog` is accepted in the profile.
- `date_from_unix_date`, `unix_seconds`, `div` and `count_if` exist on the SQL warehouse.
- The expected warnings in EXPLANATION section 3.6 are predictions from the anomaly manifest.

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Silver not yet validated (Phase 03 results missing) | Gold built on wrong data | Step 0 runs the Phase 03 checks first |
| OAuth re-prompts for every command | Slow manual runs | Token target with a short-lived token |
| Warehouse time zone assumptions | Wrong business dates | The macro does not depend on the session time zone |
| A mart join fans out | Inflated totals | Step 7 recomputes every total from silver |

## Human outputs required

- Step 0:
  - `python -m pytest -q` in `.venv`: `40 passed in 12.74s` (2026-10-31).
  - Anomalous legacy rerun and Phase 03 query results: reported verified on 2026-11-01. Phases 02 and 03 are committed together with this phase.
- Step 1, first attempt (2026-10-31): failed.
  - `.venv-dbt` was created with `python -m venv` from inside `.venv`, so it used Python 3.15.
  - pip resolved dbt-databricks 1.13.0 with dbt-core 1.11.16 and pydantic 2.12.5.
  - Building `pydantic-core` 2.41.5 failed: "the configured Python interpreter version (3.15) is newer than PyO3's maximum supported version (3.14)".
  - The runbook now recreates the environment with `python3.12` and checks the version.
- Step 1, second attempt (2026-10-31):
  - Python 3.12.16 in `.venv-dbt`; every package installed from a wheel.
  - `dbt --version`: Core 1.12.6; plugins databricks 1.13.0 and spark 1.10.3. The spark plugin is pulled in and capped below 1.11 by dbt-databricks.
  - dbt printed that dbt v2 is available and the default for new installations. The project stays on dbt Core v1.
  - `requirements-dbt.txt` is now pinned to `dbt-core==1.12.6` and `dbt-databricks==1.13.0`, so a fresh install cannot move to a different major version.
- Step 2:
  - `databricks auth describe`: workspace host found (kept out of git), profile `syukrifadzil`, auth type `databricks-cli`.
  - `databricks warehouses list`: one warehouse, "Serverless Starter Warehouse", 2X-Small, stopped.
  - `.env` filled with the profile, host and HTTP path. The token is left empty.
- Steps 3 and 5 to 8: reported verified on 2026-11-01. Outputs not pasted.
- Step 4: `dbt debug` passed with the default `oauth` target. The browser sign-in used the maintainer's Databricks account, and no token was needed.
- Step 9 (2026-11-01, first attempt):
  - `dbt docs generate` (target `oauth`): found 9 models, 31 data tests, 5 sources; `Catalog written to dbt/target/catalog.json`. It printed five agate `RuntimeWarning` lines about `table_owner`, `comment` and `table_comment` not matching a column; they did not stop the run.
  - `dbt docs serve --port 8080` failed: `OSError: [Errno 48] Address already in use`. The runbook troubleshooting table now covers this.
  - `lsof -nP -iTCP:8080 -sTCP:LISTEN`: the port is held by Docker (`com.docke...`, listening on `*:8080`), not by an earlier dbt server. Docker is left running; the next attempt serves the docs on port 8081.
  - Second attempt, on port 8081: docs served (two screenshots).
    - `mart_daily_sales`: described as "One row per Asia/Kuala_Lumpur business date with any order or any succeeded payment". Every column has its description. Types: `business_date` date; the three counts bigint; `gross_sales`, `charges`, `refunds` and `net_payments` decimal(18,2). `business_date` carries the unique and not_null tests. Depends on `stg_order_items`, `stg_orders` and `stg_payments`.
    - Lineage graph for `+mart_daily_sales+`: `silver.order_items`, `silver.orders` and `silver.payments`, each feeding its staging view, all three feeding `mart_daily_sales`. This matches the model. The runbook said "five sources", which holds only for the whole-project graph; Step 9 is corrected.  - Whole-project lineage graph: not reported.
  - Unity Catalog lineage (optional): not reported.
- Step 10: reported verified on 2026-11-01.
- Step 12 (2026-11-01): commit `6f4ff73`, pushed to `main` (`4ae4be1..6f4ff73`), 39 files changed.
  - The staged-files check printed `no local or generated files staged`.
  - The secret scan matched two lines, both false positives: a link to `docs.databricks.com` and the `dbc-xxxx` placeholder in the runbook. The scan in Step 12 now filters both out.
  - The commit included `dbt/.user.yml`. dbt writes this anonymous usage-tracking id next to `profiles.yml`, which here is `dbt/`. It holds no credentials. A follow-up commit removes it from the index and adds `.user.yml` to `.gitignore`. It stays in the history of `6f4ff73`, which was judged acceptable for a random id.
- Any failures, with the full output:

## Phase 05 prerequisites

1. Phase 04 complete and committed.
2. Decide how a scheduled run would authenticate dbt. OAuth user-to-machine cannot run unattended; Phase 05 compares a job dbt task (FE10), a token, and keeping dbt manual.
3. The Databricks CLI `bundle` commands are available (`databricks bundle --help`). Phase 05 checks the current name of the bundle product before writing configuration.
4. Explicit approval to start Phase 05.
