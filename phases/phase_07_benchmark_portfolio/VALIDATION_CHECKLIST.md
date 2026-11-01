# Phase 07 Validation Checklist

Tick each item only after doing it yourself. Items marked (evidence) need output pasted into `HANDOFF.md`. Nothing on this page is pre-filled with a result.

## Review

- [ ] `benchmarks/collect.py` reviewed: keeps only ids, times and states from the job JSON; skips runs already recorded
- [ ] Scenarios B1 to B6 agreed, including the Lakehouse on the small preset only (EXPLANATION section 4)
- [ ] ADRs 0007 and 0008 read; ADR 0009 accepted or changed
- [ ] `docs/migration_narrative.md`, `docs/limitations.md` and `docs/interview_talking_points.md` read. Every number has a source, and nothing claims more than the HANDOFFs record
- [ ] README Results table matches the Phase 06 HANDOFF
- [ ] No emojis, authorship trailers or unsupported claims in any file

## Local

- [ ] Step 1: `48 passed` (evidence)
- [ ] Step 2: environment recorded in RESULTS.md section 1 (evidence)
- [ ] Step 3: B1, three rows added (evidence)
- [ ] Step 4: B2, three rows added; medium data present or generated and validated (evidence)

## Workspace

- [ ] Step 5: reference layer counts taken; B3, three runs `TERMINATED SUCCESS`, `RESULT: PASS`, 4 rows each (evidence)
- [ ] Step 6: B4, the Phase 06 runs collected, or B-V4 recorded as false (evidence)
- [ ] Step 7: B5, full refresh `COMPLETED`; `pipeline_updates.sql` row recorded; layer counts identical to Step 5 (evidence)
- [ ] Step 8: B6, `RESTORE` runtime recorded; clean headline after the restore; roll forward PASS; anomalous headline (evidence)
- [ ] Step 9 (optional): usage quantities recorded, or B-V3 recorded as false (evidence)

## Results

- [ ] Step 10: summary table pasted into RESULTS.md section 2; notes filled
- [ ] RESULTS.md sections 4 and 5 filled from recorded runs, each with its evidence
- [ ] Every number in RESULTS.md has a source in `runs.csv`, a SQL result or a HANDOFF
- [ ] No speed comparison between the legacy job and the Lakehouse, and no currency anywhere

## Screenshots (optional before publication)

- [ ] Captured per `docs/screenshots_checklist.md`
- [ ] Each image checked by eye: no host, workspace id, email, signed link or other tabs

## Commit

- [ ] Step 12: no local or generated files staged; secret scan and email check clean
- [ ] CI after the push: `unit-tests` shows `48 passed` with no skips (evidence)

## Publication (Step 13)

- [ ] Licence chosen and added; README License section updated
- [ ] History scan: `history clean`, `no ignored files in history`
- [ ] Commit author emails reviewed; decision recorded
- [ ] Repository description and topics set
- [ ] README rendered on GitHub: diagrams and links work
- [ ] Visibility changed, if and when you decide to publish

## Acceptance criteria (docs/case_study.md)

- [ ] AC12: benchmark and portfolio material contains only measured numbers, with environment and caveats stated
- [ ] AC13: secret scan clean before the push, and the history scan clean before publication
- [ ] Human committed and pushed Phase 07
