# 0007. One bundle-deployed job runs the pipeline, dbt and reconciliation

- Status: Accepted (2026-11-01)
- Date: 2026-11-01

## Context

Phases 03 and 04 ran the pipeline and dbt by hand, in a fixed order. A nightly system needs that order enforced, the configuration in version control, and a run history that shows what happened. Phase 06 added a third step, the reconciliation against the legacy outputs. The deployment must stay human-operated and keep credentials out of git (ADR 0005).

## Decision

- `databricks.yml` defines a Declarative Automation Bundle with:
  - the Lakeflow pipeline, bound to the one created in Phase 03 and protected with `prevent_destroy`
  - the job `retail_nightly`
- The job has three tasks, each starting only if the one before it succeeded:
  - `bronze_silver`: the pipeline update
  - `gold`: a dbt task running `dbt build` against the SQL warehouse, looked up by name
  - `reconciliation`: a Python script task on serverless
- One job parameter, `dataset`, tells the reconciliation which legacy output and which allowed causes apply.
- The reconciliation writes its results to `retail_audit`, replacing any earlier rows for the same run id.
- One `dev` target in development mode, no schedule, one run at a time. The maintainer deploys and runs from a local terminal.

## Alternatives considered

| Option | Benefits | Drawbacks |
|---|---|---|
| Separate manual steps (pipeline, then `dbt build` locally) | No new configuration | Order and history depend on the operator; dbt needs a local connection |
| Jobs created in the UI | Quick | Not in version control; drifts from the code |
| dbt run outside Databricks (local or CI) | Familiar | Needs credentials outside the workspace, against ADR 0005 |
| Reconciliation as a separate job or a local script only | Simpler job | A gold build would not check itself; the evidence would depend on remembering a second step |
| Bundle job with three tasks (chosen) | Versioned, ordered, one run history, no credentials in git | Bundle and task behaviour on Free Edition had to be verified (Phases 05 and 06) |

## Consequences

- **A failure stops the run.** A failed reconciliation fails the run: it is the last task, so nothing downstream is skipped, and the run status is the signal.
- **Rows per run id.** The platform ran a failed serverless task a second time under the same run id, although the job sets no retries (Phase 06 HANDOFF). The reconciliation therefore writes its results per run id rather than appending.
- **Production would add** a schedule, alerts on failure, a service principal as the run identity, and separate targets per environment (docs/case_study.md section 7).

## Verification required

All confirmed on 2026-11-01:
- **Phase 05:** bundle validation, binding, deployment and a successful run.
- **Phase 06:**
  - the Python script task on serverless
  - `--params` and `--only gold+`
  - the failure path (R8)
  - the idempotent results write
