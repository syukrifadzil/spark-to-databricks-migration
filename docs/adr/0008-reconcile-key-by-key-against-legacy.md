# 0008. Reconcile gold with the legacy outputs key by key, and explain differences by cause

- Status: Accepted (2026-11-01)
- Date: 2026-11-01

## Context

AC10 asks for exact agreement with the legacy job on clean data and an explanation for every difference on anomalous data. The legacy job is wrong by design on the clean feed: it applies late arrivals in file order and counts replays twice (Phase 02, L3 and L4). Totals alone can hide errors that cancel out.

## Decision

- **Compare key by key.** Collapse each mart to one row per key on both sides, hash the row and join on the key with null-safe equality. Classify each difference as missing, duplicate or value mismatch, and print the column totals as well.
- **Use legacy `ordered` for the exact match.** It is the legacy job run on a dataset with the same final state and no late or replayed deliveries, so the legacy rules give the right answer there.
- **Explain differences by touched keys.** A difference is explained only if a documented cause touches its key. The causes come from the generator's manifests: late arrivals and replays in the clean feed, and the rows of each anomaly batch. A duplicate key in gold is never explained.
- **Two implementations.** The check runs as the job's last task (ADR 0007). An independent SQL version (`reconciliation/sql/02_legacy_vs_gold.sql`) recomputes the counts.

## Alternatives considered

| Option | Drawback |
|---|---|
| Compare the baseline metrics (sums and counts) only | Differences can cancel out; it does not say which rows differ |
| Exact match against legacy `clean` | Would require gold to copy the legacy bugs |
| A ledger of expected differences per scenario | Tied to one seed and data size; recomputed by hand on every change |
| Re-implement the legacy rules to predict its output | A second copy of the logic under test |

## Consequences

- **Accepted trade-off:** a real defect on a key that a cause also touches would be counted as explained. The exact comparison, with no causes, limits this. So does the comparison of anomalous gold against `ordered`, which allows only the two scenarios that change silver.
- **Results are queryable.** They are kept in `retail_audit`, so every run's reconciliation can be checked in SQL.

## Verification required

Confirmed on 2026-11-01 (Phase 06 HANDOFF):
- **Clean state:** 0 differences against `ordered` on all three marts.
- **Anomalous state:** 0 unexplained differences.
- **The SQL cross-check** gave the same counts as the task.
- **The negative test** failed on exactly the 2 dates and 5 customers that the anomaly scenarios change.
