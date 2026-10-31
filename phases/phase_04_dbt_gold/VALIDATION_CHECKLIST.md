# Phase 04 Validation Checklist

Tick each item only after doing it yourself. Items marked (evidence) need output pasted into `HANDOFF.md`.

## Review

- [ ] Implementation reviewed by human: models, `_sources.yml`, `_marts.yml`, business tests
- [ ] Mart SQL matches `docs/data_contracts.md` section 7
- [ ] Severity rule agreed: error for pipeline or model defects, warn for source data problems
- [ ] No emojis, authorship trailers or unsupported claims in any file

## Before dbt

- [ ] Step 0: Phase 02 and Phase 03 checks pass and both phases are committed (evidence)

## dbt

- [ ] Step 1: dbt installed in `.venv-dbt`; versions recorded (evidence)
- [ ] Step 3: `git check-ignore` reports both `dbt/profiles.yml` and `.env` (evidence)
- [ ] Step 4: `dbt debug` passes; target used recorded (evidence)
- [ ] Step 5: `dbt build` with `ERROR=0` and exactly the four expected warnings (evidence)
- [ ] Step 6: the five overpaid orders match the anomaly manifest (evidence)
- [ ] Step 7: all 12 gold checks `ok`; headline numbers recorded (evidence)
- [ ] Step 8: `retail_gold` holds only the eight dbt objects; `retail_silver` nothing from dbt (evidence)
- [ ] Step 9: docs lineage shows sources, staging, marts
- [ ] Step 10: a second build gives identical results (evidence)

## Acceptance criteria (docs/case_study.md)

- [ ] AC7: dbt builds gold from silver only; every schema test passes and every business test result is explained (Steps 5, 6)
- [ ] AC8: ownership enforced (Step 8)
- [ ] AC13: secret scan clean; `profiles.yml` and `.env` not staged (Step 12)
- [ ] Human committed and pushed Phase 04
