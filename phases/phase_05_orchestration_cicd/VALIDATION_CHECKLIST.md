# Phase 05 Validation Checklist

Tick each item only after doing it yourself. Items marked (evidence) need output pasted into `HANDOFF.md`.

## Review

- [ ] `databricks.yml` reviewed: pipeline settings match `lakeflow/pipeline.json` apart from the code paths; the job has two tasks in the right order
- [ ] `.github/workflows/ci.yml` reviewed: no secrets, `permissions: contents: read`, no deployment step
- [ ] Decisions agreed: bind instead of a new pipeline (D2), no schedule (D5), single `dev` target (D7), no linter yet (D10), no deploy workflow (D11)
- [ ] No emojis, authorship trailers or unsupported claims in any file

## Before the workspace

- [ ] Step 0: Phase 04 `.user.yml` follow-up committed and pushed (evidence)
- [ ] Step 1: CLI version recorded; `bind` available (evidence)
- [ ] Step 2: `41 passed` (evidence)
- [ ] Step 3: `Validation OK!`; resolved paths under `.bundle/.../dev/files`; warehouse id resolved (evidence)

## Workspace

- [ ] Step 4a: layer counts recorded before the bind (evidence)
- [ ] Step 4b: pipeline `65b949fd-...` bound (evidence)
- [ ] Step 5: deploy reports `1 created, 1 changed, 0 deleted`; `summary` shows the same pipeline id; pipeline reads code from the bundle; no git-ignored file uploaded (evidence)
- [ ] Step 6: job run succeeded; `gold` shows `ERROR=0` and the four expected warnings (evidence)
- [ ] Step 7: layer counts identical to Step 4a; 12 gold checks `ok`; headline numbers unchanged (evidence)
- [ ] Step 8: FE9, FE10, FE12 and FE14 findings recorded (evidence)

## CI

- [ ] Step 10: secret scan clean; no local or generated files staged
- [ ] Step 11: CI run green; `unit-tests` shows 41 passed with no skips; `dbt-parse` passed (evidence)

## Acceptance criteria (docs/case_study.md)

- [ ] AC5: rerun with no new files leaves silver unchanged, through the job (Step 7)
- [ ] AC9: GitHub Actions runs static checks and unit tests with no workspace secrets (Step 11)
- [ ] AC13: secret scan clean before the push (Step 10)
- [ ] Human committed and pushed Phase 05
