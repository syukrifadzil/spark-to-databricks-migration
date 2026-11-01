# Spark to Databricks Migration

A case study in migrating a legacy batch PySpark ETL for a fictional Malaysian retailer to a Databricks Lakehouse built on Lakeflow Declarative Pipelines, Delta Lake, Unity Catalog and dbt Core, with GitHub Actions for continuous integration.

**Status:** Phases 00 to 06 are complete and validated by the maintainer:
- the foundation and synthetic data
- the legacy job
- Lakeflow bronze and silver, and the dbt gold marts
- orchestration and CI. A bundle deploys the pipeline and the job `retail_nightly`, and GitHub Actions runs the checks without secrets.
- reconciliation and resilience. A third job task reconciles gold with the legacy outputs key by key:
  - on the clean state, gold matches the legacy job's correct output exactly
  - on the anomalous state, every difference has a documented cause
  - a test matrix covers reruns, replays, bad records, schema drift, late arrivals, recovery and rollback

Phase 07 (benchmark and portfolio) is validated by the maintainer. Its measured runtimes are in [benchmarks/RESULTS.md](benchmarks/RESULTS.md). The legacy job and the Lakehouse are not compared on speed, because they run on different hardware and start-up dominates both at this size.

## Results

Recorded on Databricks Free Edition with the small synthetic preset, 2026-11-01. The evidence is in [the Phase 06 handoff](phases/phase_06_reconciliation_resilience/HANDOFF.md).

| Check | Result |
|---|---|
| Gold against the legacy output on correctly ordered data | 94 / 530 / 50 rows on the three marts, 0 differences |
| Gold against the legacy output on anomalous data | Every difference explained by a documented cause; 0 unexplained |
| Deliberate wrong-dataset run | Job failed on exactly the 2 dates and 5 customers the anomalies change |
| Quarantined rows against the anomaly manifest | 35 of 35 |
| Rerun, replay, late re-delivery, full refresh, gold `RESTORE` | Silver unchanged or restored; gold rolled back and forward |

The project does not claim production readiness or a speed advantage. See [docs/limitations.md](docs/limitations.md).

## What the project demonstrates

- Rebuilding a full-overwrite batch job as incremental, idempotent ingestion with Auto Loader and change-data-capture upserts.
- Explicit data quality: declared rules, quarantine tables with failure reasons, and observable counts.
- Clear tool ownership: Lakeflow for bronze and silver, dbt Core for gold marts.
- Proving correctness by reconciling legacy and modern outputs on identical, deterministic synthetic data.
- Running on Databricks Free Edition with documented assumptions and fallbacks.

## Architecture at a glance

![System context: local workstation, Databricks workspace and GitHub, with numbered data flow from generation through reconciliation](docs/diagrams/system-context.svg)

| Layer | Schema | Owner |
|---|---|---|
| Landing | `retail_landing` (volume `raw`) | Manual upload |
| Bronze | `retail_bronze` | Lakeflow pipeline |
| Silver and quarantine | `retail_silver` | Lakeflow pipeline |
| Gold | `retail_gold` | dbt Core |
| Reconciliation results | `retail_audit` | Reconciliation job task |

Full design: [docs/architecture.md](docs/architecture.md).

## Phases

| Phase | Scope | Status |
|---|---|---|
| 00 | Foundation: architecture, contracts, ADRs, conventions | Complete |
| 01 | Synthetic data generation and data contracts | Complete |
| 02 | Legacy PySpark job | Complete |
| 03 | Lakeflow bronze and silver | Complete |
| 04 | dbt gold marts | Complete |
| 05 | Orchestration and CI/CD | Complete |
| 06 | Reconciliation and resilience | Complete |
| 07 | Benchmark and portfolio | Validated; publication pending |

Each phase folder under `phases/` contains the phase brief (`PROMPT.md`), a design explanation, a manual runbook, a validation checklist and a handoff note.

## Repository layout

Directories are created by the phase that first needs them.

```
.
├── README.md
├── GLOBAL_MASTER_INSTRUCTIONS.md   Project-wide working rules
├── .gitignore
├── .env.example                    Variable names only; copy to .env locally
├── pyproject.toml                  pytest settings
├── requirements-dev.txt            Test dependency (Phase 01 code is standard library only)
├── requirements-spark.txt          PySpark for the legacy job (needs Java 17 or 21)
├── requirements-dbt.txt            dbt Core and dbt-databricks, in their own .venv-dbt
├── databricks.yml                  Bundle: pipeline and job retail_nightly (05)
├── docs/
│   ├── case_study.md               Scenario, goals, acceptance criteria
│   ├── architecture.md             Target architecture and diagrams
│   ├── data_contracts.md           Contract framework and quality rules
│   ├── platform_assumptions.md     Free Edition, cost, toolchain, responsibilities
│   ├── diagrams/                   Architecture diagrams (SVG)
│   └── adr/                        Architecture decision records
├── infra/sql/                      Workspace setup SQL (00)
├── data/                           Generator, contracts, samples (01)
├── legacy_spark/                   Legacy batch job (02)
├── lakeflow/                       Pipeline source, contract rules, settings, checks (03)
├── dbt/                            dbt project: sources, staging, marts, tests (04)
├── .github/workflows/              CI (05)
├── reconciliation/                 Legacy versus gold reconciliation task and SQL checks (06)
├── benchmarks/                     Results collector, SQL, recorded results (07)
├── tests/                          Unit tests
└── phases/                         Per-phase briefs and documentation
```

## Getting started

Requires Python 3.10 or later. Follow the runbooks in order:

1. [Phase 00: workspace and repository setup](phases/phase_00_foundation/MANUAL_RUNBOOK.md)
2. [Phase 01: generate and validate the synthetic data](phases/phase_01_synthetic_data/MANUAL_RUNBOOK.md)
3. [Phase 02: run the legacy job](phases/phase_02_legacy_spark/MANUAL_RUNBOOK.md)
4. [Phase 03: deploy and run the Lakeflow pipeline](phases/phase_03_lakeflow_bronze_silver/MANUAL_RUNBOOK.md)
5. [Phase 04: build and test the gold marts with dbt](phases/phase_04_dbt_gold/MANUAL_RUNBOOK.md)
6. [Phase 05: deploy the bundle, run the job, check CI](phases/phase_05_orchestration_cicd/MANUAL_RUNBOOK.md)
7. [Phase 06: reconcile with the legacy outputs and run the resilience tests](phases/phase_06_reconciliation_resilience/MANUAL_RUNBOOK.md)
8. [Phase 07: record the benchmarks and publish](phases/phase_07_benchmark_portfolio/MANUAL_RUNBOOK.md)

Quick start for the data, from the repository root:

```bash
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m data.generators.generate --preset small --out data/raw/clean
python -m data.generators.validate --data data/raw/clean

# Legacy job (needs Java 17 or 21)
python -m pip install -r requirements-spark.txt
python -m legacy_spark.retail_nightly_job --input data/raw/clean --output output/legacy/clean
```

## Documentation

- [Case study, goals and acceptance criteria](docs/case_study.md)
- [Target architecture](docs/architecture.md)
- [Data contracts](docs/data_contracts.md)
- [Platform and cost assumptions](docs/platform_assumptions.md)
- [Architecture decision records](docs/adr/README.md)
- [Migration narrative](docs/migration_narrative.md): what was built, what the evidence shows, what went wrong
- [Limitations](docs/limitations.md)
- [Benchmarks](benchmarks/README.md) and [results](benchmarks/RESULTS.md)
- [Interview talking points](docs/interview_talking_points.md)
- [Screenshots checklist](docs/screenshots_checklist.md)

## Security

Never commit `.env`, `profiles.yml`, `~/.databrickscfg`, tokens or bulk generated data. The `.gitignore` covers these; each runbook includes a scan of staged changes before pushing.

## Limitations

Databricks Free Edition is a non-commercial environment with quotas and no SLA. Nothing here implies production readiness; see the demo versus production table in [docs/case_study.md](docs/case_study.md).

## License

Licensed under either of

- Apache License, Version 2.0 ([LICENSE-APACHE](LICENSE-APACHE))
- MIT License ([LICENSE-MIT](LICENSE-MIT))

at your option (`SPDX-License-Identifier: MIT OR Apache-2.0`). All data in this repository is synthetic.
