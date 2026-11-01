# 0009. Benchmark with measured wall-clock proxies only, and no speed comparison

- Status: Accepted (2026-11-01)
- Date: 2026-11-01

## Context

The portfolio needs runtime and cost evidence (AC12). The two systems run on different hardware: a laptop JVM and Databricks serverless compute. Free Edition has no billing, and its quotas are not documented (FE13). At the small preset, start-up time dominates both systems. Phase 02 measured the legacy job at 9.0 s on small and 9.7 s on medium.

## Decision

- **Measure wall-clock seconds from each system's own records.** That means `duration_seconds` from the legacy job, run and task times from the Jobs API, update events from the pipeline event log, and SQL editor runtimes.
- **Record every run in `benchmarks/results/runs.csv`** and report the median with the minimum and maximum.
- **Never present a faster or slower comparison between the two systems.** Present what each one has to redo: a full reload against an incremental update.
- **Never publish prices or DBU rates.** Usage quantities are recorded only if the billing system table is readable.
- **Run the Lakehouse on the small preset only.** The legacy job also runs on medium.

## Alternatives considered

| Option | Drawback |
|---|---|
| Report a speed-up factor | Compares a laptop with cloud compute; misleading at any size |
| Estimate cost from published DBU prices | Free Edition does not bill; the estimate would not be a measurement |
| Run the Lakehouse on the medium preset | Replaces the landing data and the Phase 06 state; quota risk on Free Edition |
| Timing by stopwatch or CLI output only | Not reproducible; includes client-side waiting |

## Consequences

- The results show behaviour (what each run reads and rebuilds) more than speed.
- The harness is a small standard-library script with a unit test. It keeps workspace URLs and user names out of git by recording only ids, times and states.

## Verification required

- Phase 07 runbook: B-V1 to B-V4 in `benchmarks/README.md`.
