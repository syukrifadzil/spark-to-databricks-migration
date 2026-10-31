# Phase 02 Validation Checklist

Tick each item only after doing it yourself. Items marked (evidence) need output pasted into `HANDOFF.md`.

## Review

- [ ] Implementation reviewed by human
- [ ] Mart business rules in `docs/data_contracts.md` section 7 agreed: they bind Phase 04 too
- [ ] Legacy semantics agreed: last file wins for customers, products and orders; items and payments stacked without deduplication
- [ ] The ten limitations in `EXPLANATION.md` section 4 agreed, including the two deliberate non-legacy choices (pinned time zone, deterministic last-file-wins)
- [ ] No emojis, authorship trailers or unsupported claims in any file

## Environment

- [ ] Java version recorded (evidence)
- [ ] PySpark version and the Python environment used recorded (evidence)
- [ ] Spark smoke test printed `rows: 3`

## Tests and runs

- [ ] `python -m pytest -q` reports 34 passed (evidence)
- [ ] Samples run: 49 customer rows, 15 product rows, no null-date rows, three equal gross sales metrics (evidence)
- [ ] Small and medium runs complete; row counts 530 and 5150 customers, 50 and 500 products (evidence)
- [ ] Runtimes recorded from `time` and `duration_seconds`, with the Spark version (evidence)
- [ ] Anomalous run completes; metric differences recorded and compared with the predictions in `EXPLANATION.md` section 5 (evidence)
- [ ] Optional: ordered dataset generated, validated and run

## Acceptance criteria for Phase 02 (AC3 in docs/case_study.md)

- [ ] AC3: the legacy job runs locally on the generated data and writes baseline outputs plus baseline reconciliation metrics
- [ ] No `output/`, `data/raw/` or `.venv*` files staged
- [ ] Human executed manual validation
- [ ] Evidence and failures recorded in `HANDOFF.md`
- [ ] Human committed and pushed changes
