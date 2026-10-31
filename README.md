# Spark to Databricks Migration

A case study in migrating a legacy batch PySpark ETL for a fictional Malaysian retailer to a Databricks Lakehouse built on Lakeflow Declarative Pipelines, Delta Lake, Unity Catalog and dbt Core, with GitHub Actions for continuous integration.

**Status:** Phases 00 to 05 are complete and validated by the maintainer:
- the foundation and synthetic data
- the legacy job
- Lakeflow bronze and silver, and the dbt gold marts
- orchestration and CI. A bundle deploys the pipeline and the job `retail_nightly`, and GitHub Actions runs the checks without secrets. Results are added only from recorded runs.

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
| 06 | Reconciliation and resilience | Not started |
| 07 | Benchmark and portfolio | Not started |

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
├── reconciliation/                 Legacy versus modern checks (06)
├── benchmarks/                     Harness and recorded results (07)
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

## Security

Never commit `.env`, `profiles.yml`, `~/.databrickscfg`, tokens or bulk generated data. The `.gitignore` covers these; each runbook includes a scan of staged changes before pushing.

## Limitations

Databricks Free Edition is a non-commercial environment with quotas and no SLA. Nothing here implies production readiness; see the demo versus production table in [docs/case_study.md](docs/case_study.md).

## License

To be chosen before publication (Phase 07).
