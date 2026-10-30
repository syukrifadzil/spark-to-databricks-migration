# Phase 00 Validation Checklist

Tick each item only after doing it yourself. Items marked (evidence) need an output or screenshot recorded in `HANDOFF.md`.

## Review

- [ ] Implementation reviewed by human
- [ ] `docs/case_study.md` goals and acceptance criteria agreed, or changes requested
- [ ] `docs/architecture.md` layer ownership agreed (Lakeflow bronze and silver, dbt gold)
- [ ] `docs/data_contracts.md` conventions agreed: UTC timestamps, `Asia/Kuala_Lumpur` business date, `DECIMAL(18,2)` MYR, half-up rounding
- [ ] Anomaly-to-behaviour table agreed, in particular that invalid references are flagged rather than quarantined
- [ ] Each ADR 0001 to 0006 marked Accepted, or comments recorded
- [ ] No emojis, authorship trailers or unsupported claims in any file

## Local environment

- [ ] Tool versions recorded: macOS, Homebrew, Git, Python, Java if installed (evidence)
- [ ] `.env` created from `.env.example` with `-rw-------` permissions
- [ ] `git check-ignore -v .env` reports `.env` as ignored (evidence)
- [ ] `git status --short` does not list `.env`

## Workspace

- [ ] Free Edition workspace accessible; host recorded locally only
- [ ] FE1, FE2, FE5, FE6, FE8, FE9, FE11 observations filled in `docs/platform_assumptions.md`
- [ ] `infra/sql/00_create_namespace.sql` ran without error (evidence)
- [ ] `SHOW SCHEMAS LIKE 'retail_*'` returned four schemas (evidence)
- [ ] `SHOW VOLUMES IN retail_landing` returned `raw` (evidence)
- [ ] Script re-run succeeded with no errors (idempotency)
- [ ] Optional: FE4 catalog probe result recorded
- [ ] Optional: Databricks CLI authenticated; `databricks current-user me` returned your user (evidence, redact anything sensitive)

## Acceptance criteria for Phase 00

- [ ] All required files present (Runbook Step 1)
- [ ] All seven SVG diagrams display correctly locally and on GitHub (no overflowing text or misplaced arrows)
- [ ] Any FE item observed as unavailable has its fallback noted in `HANDOFF.md`
- [ ] Secret scan before commit returned no matches (evidence)
- [ ] Human executed manual validation
- [ ] Evidence and failures recorded in `HANDOFF.md`
- [ ] Human committed and pushed changes
