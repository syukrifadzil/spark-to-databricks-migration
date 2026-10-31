# Phase 01 Validation Checklist

Tick each item only after doing it yourself. Items marked (evidence) need output pasted into `HANDOFF.md`.

## Review

- [ ] Implementation reviewed by human
- [ ] `data/contracts/retail_contract.json` matches `docs/data_contracts.md` section 4 (columns, allowed values, ranges)
- [ ] Order lifecycle paths and refund handling in `EXPLANATION.md` section 5.2 agreed
- [ ] Decision P5 agreed: late arrivals and replays are part of clean data, listed in the manifest
- [ ] Deviations from the brief agreed: single generator script (P2), flat `batch_NNN` folders (P3), no fixture folders (P7), standard library only (P1)
- [ ] No emojis, authorship trailers or unsupported claims in any file

## Environment

- [ ] Python version is 3.10 or later (evidence)
- [ ] Virtual environment created; `pytest --version` recorded (evidence)

## Correctness

- [ ] Tiny dataset validates with `PASS` (evidence)
- [ ] `python -m pytest -q` reports 30 passed (evidence)
- [ ] Small and medium datasets validate with `PASS` (evidence)
- [ ] Exact counts match: small snapshot 500/50/5000, final customers 530 and orders 5300; medium snapshot 5000/500/50000, final customers 5150 and orders 53000 (evidence)

## Reproducibility

- [ ] Two small runs with the same seed are identical (`diff -r` prints nothing, `IDENTICAL`) (evidence)
- [ ] A different seed produces different files (evidence)

## Anomalies

- [ ] `--all` injection validates with `PASS`; every scenario count recorded (evidence)
- [ ] Single-scenario injection writes only its own batch and validates with `PASS`
- [ ] Clean dataset still validates after injection (integrity unchanged)

## Data inspection

- [ ] Headers, timestamps and amounts look as documented
- [ ] Nothing resembles real personal data; emails use example domains only

## Acceptance criteria for Phase 01 (AC1, AC2 in docs/case_study.md)

- [ ] AC1: same seed, as-of date and preset give byte-identical files
- [ ] AC2: clean data passes every contract check; each anomaly appears only when enabled and is listed in the manifest
- [ ] Generation time and folder size recorded for small and medium (evidence)
- [ ] Samples generated under `data/samples/` and validated
- [ ] No `data/raw/`, `.venv/` or cache files staged
- [ ] Human executed manual validation
- [ ] Evidence and failures recorded in `HANDOFF.md`
- [ ] Human committed and pushed changes
