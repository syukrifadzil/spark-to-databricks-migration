# Phase 03 Validation Checklist

Tick each item only after doing it yourself. Items marked (evidence) need output pasted into `HANDOFF.md`.

## Review

- [ ] Implementation reviewed by human: `lakeflow/transformations/retail_pipeline.py`, `lakeflow/retail_rules.py`, `lakeflow/pipeline.json`
- [ ] The handling table in `EXPLANATION.md` section 3.5 agreed, in particular: invalid updates leave the previous valid version in silver; orphans are kept
- [ ] The API verification table (`EXPLANATION.md` section 4) read, with its open items understood
- [ ] No emojis, authorship trailers or unsupported claims in any file

## Before the workspace

- [ ] Step 0: `pytest -q` reports 38 passed (evidence)
- [ ] Step 0: anomalous legacy metrics print `5310.00 4472.00`, closing Phase 02 O1 (evidence)
- [ ] Step 0: Phase 02 committed and pushed separately (commit hash)

## Workspace

- [ ] Step 3: code and contract uploaded; `get-status` shows `FILE` for both (evidence)
- [ ] Step 4: landing folder holds `batch_000` to `batch_003`, `_expected`, `_manifest.json` (evidence)
- [ ] Step 5: pipeline created with serverless, catalog `workspace`, schema `retail_silver` (evidence)
- [ ] Step 6: first update completed; 25 datasets in the graph (evidence)
- [ ] Step 7: layer counts match; silver equals `_expected` with all zeros (evidence)
- [ ] Step 8: rerun with no files leaves counts and fingerprints unchanged (evidence)
- [ ] Step 9: replayed batch grows bronze by the stated amounts; silver unchanged (evidence)
- [ ] Step 10: anomaly batches give the stated counts; all 18 anomaly checks `ok` (evidence)
- [ ] Step 11: full refresh reproduces Step 10 exactly (evidence)
- [ ] Step 11a, if Steps 8 to 10 were not separated: `02` shows only the anomaly differences; a rerun with no files and the `batch_901` replay leave silver unchanged (evidence)

## Acceptance criteria (docs/case_study.md)

- [ ] AC4: snapshot and three incremental batches ingested into bronze and silver (Steps 6, 7)
- [ ] AC5: no change on a rerun without files, or on a replayed batch (Steps 8, 9)
- [ ] AC6, Phase 03 part: every row-level anomaly quarantined, sequenced, kept or rescued as the manifest expects (Step 10). The business-rule anomaly (payment_mismatch) is completed in Phase 04 and 06
- [ ] AC8, Phase 03 part: the pipeline writes only to `retail_bronze` and `retail_silver` (graph in Step 6)
- [ ] No `output/`, `data/raw/` or `.venv*` files staged
- [ ] Evidence and failures recorded in `HANDOFF.md`
- [ ] Human committed and pushed Phase 03
