# Limitations

What this project does not show, and where its evidence is weaker than it may look. The production hardening table in [case_study.md](case_study.md) section 7 lists what a real deployment would add.

## Platform

- **Not a production platform.** Databricks Free Edition is for non-commercial use, with no SLA and with quotas that are not fully documented (FE13, FE15 in [platform_assumptions.md](platform_assumptions.md)). The project shows mechanisms, not production readiness.
- **One workspace, one catalog, one target.** Promotion between environments is not exercised.
- **Personal identity.** The job runs as the maintainer, not as a service principal.

## Data

- **Synthetic, small data.** All data is synthetic, from one seed. The Lakehouse ran on the small preset only: 530 customers, 50 products and 5,300 orders in the final state. Behaviour at scale is not measured.
- **Built-in anomalies only.** Each of the ten scenarios appears once. Combinations and rare edge cases beyond them are not generated.
- **Manual landing.** Files are uploaded by hand, and in R6 they were deliberately removed and delivered again. A source system feeding an external location is not modelled.

## Correctness evidence

- **Cause-based explanations are a trade-off.** A difference counts as explained when a documented cause touches its key. A real defect on such a key would also count as explained (ADR 0008). The exact comparison against the legacy `ordered` output, with no causes, is the check that limits this.
- **The legacy job is a stand-in.** It was written for this project to behave like a typical legacy job. Reconciling against it shows agreement with documented rules, not with a real system of record.
- **Some results were reported, not transcribed.** The maintainer ran every step, but for some steps they reported that the results matched the runbook instead of pasting them: parts of Phases 02 to 04 and the final Phase 06 runs. Each HANDOFF marks which results are transcribed and which are reported.

## Benchmarks

- **No speed comparison between the systems.** Laptop and serverless compute are different hardware, and at this size start-up dominates both. The benchmark records what each system redoes, not which is faster (ADR 0009).
- **No cost in currency.** Free Edition has no billing. Usage quantities appear only if the billing system table is readable.

## Operations

- **No unattended operation.** There is no schedule, no alerting and no on-call. A failed run is visible only in the run history.
- **The platform's own retry.** A failed serverless task was run a second time under the same run id although the job sets no retries. The reconciliation tolerates this, but the behaviour is observed, not documented.
- **Silver history cannot be queried.** The pipeline's streaming tables refused time travel. A past silver state can be checked only while it lasts. Gold history can be queried and restored.
- **CI does not reach the workspace.** It runs unit tests, `dbt parse` and a token scan. Integration testing is manual (ADR 0005).
