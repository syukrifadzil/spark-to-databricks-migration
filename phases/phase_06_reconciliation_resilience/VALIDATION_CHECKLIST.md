# Phase 06 Validation Checklist

Tick each item only after doing it yourself. Items marked (evidence) need output pasted into `HANDOFF.md`. Nothing on this page is pre-filled with a result.

## Review

- [ ] `reconciliation/reconcile.py` reviewed: the touch rules in `touched_keys` match EXPLANATION section 4.3
- [ ] Acceptable differences agreed (EXPLANATION section 5.2), and the invariants accepted (section 5.1)
- [ ] Decisions agreed:
  - exact match against legacy `ordered` (D3)
  - clean state by removal and full refresh (D4)
  - new schema `retail_audit` (D6)
  - legacy outputs under `raw/legacy/` (D7)
- [ ] No emojis, authorship trailers or unsupported claims in any file

## Local

- [ ] Step 1: `47 passed` (evidence)
- [ ] Step 2: legacy metrics printed; `ordered` row compared with the prediction (evidence)
- [ ] Step 3: both rehearsals `RESULT: PASS`; clean totals compared with the prediction (evidence)

## Workspace

- [ ] Step 4: legacy outputs and the anomaly manifest listed in the volume; whether `batch_901` exists (evidence)
- [ ] Step 5: `Validation OK!`; reconciliation task and environment as expected; deploy `0 deleted` (evidence)
- [ ] Step 6: three tasks succeeded; `RESULT: PASS`; SQL cross-check counts equal the task's; metrics over gold; 18 anomaly checks `ok` (evidence)
- [ ] Step 7: run with `dataset=clean` on anomalous data failed in `reconciliation` with unexplained differences (evidence)
- [ ] Step 8: silver equals the expected state; exact comparison all zero; V_clean recorded (evidence)
- [ ] Step 9: counts and fingerprints identical to Step 6a; anomaly checks `ok`; `RESULT: PASS` (evidence)
- [ ] Step 10: restore gave the clean headline; roll forward gave the anomalous headline (evidence)
- [ ] Step 11: rerun identical to Step 6a, or to Step 9 if 6a was not recorded (evidence)
- [ ] Step 11b: the repeated negative test failed, and its run has 6 summary rows and 1 write (evidence)
- [ ] Step 12 (optional): replay left silver unchanged (evidence)

## Test matrix evidence

Fill in from your own runs. "Observed" is what the output showed, in a few words or numbers. "Evidence" is where the full output is: the handoff line, a run URL without the host, or a screenshot name. "Result" is pass, fail or not run.

| ID | Scenario | Runbook | Expected | Observed | Evidence | Result |
|---|---|---|---|---|---|---|
| AC10a | Exact match on clean data | 8 | Gold vs legacy `ordered`: 0 differences on all three marts | | | |
| AC10b | Every difference on anomalous data explained | 6 | Gold vs legacy `anomalous`: `unexplained 0` | | | |
| R1 | Rerun with no new files | 11 | Counts and fingerprints identical to 6a; `PASS` | | | |
| R2 | Replayed batch | 12 | Bronze +16/+206/+321/+109/+2; silver identical | | | |
| R3 | Bad records | 6d, 6b | 18 anomaly checks `ok`; gold vs `ordered` differs only on 2 dates and up to 5 customers | | | |
| R4 | Schema drift | 6d | Rescued data in 5 bronze rows; silver values unchanged | | | |
| R5a | Late versions in the feed | 6d | No silver row from `EVT-A012` | | | |
| R5b | Whole batches delivered late | 9 | State identical to 6a, fingerprints included | | | |
| R6 | Recovery from bad batches | 8 | Silver equals `_expected`; quarantine 0; exact comparison all 0 | | | |
| R7 | Gold rollback | 10 | Restore: clean headline; roll forward: anomalous headline | | | |
| R8 | Reconciliation catches a defect | 7 | Task fails with unexplained differences | | | |

## Commit

- [ ] Step 14: no local or generated files staged; secret scan clean
- [ ] CI after the push: `unit-tests` shows `47 passed` with no skips (evidence)

## Acceptance criteria (docs/case_study.md)

- [ ] AC5: rerun and replay leave silver unchanged (R1, R2)
- [ ] AC6: every anomaly accounted for (R3, and the explained differences in Step 6)
- [ ] AC10: legacy and modern reconcile (AC10a, AC10b)
- [ ] AC11: rerun, late arrival, schema drift and recovery executed and recorded (matrix above)
- [ ] AC13: secret scan clean before the push
- [ ] Human committed and pushed Phase 06
