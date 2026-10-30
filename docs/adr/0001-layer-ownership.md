# 0001. Lakeflow owns bronze and silver; dbt owns gold

- Status: Accepted (2026-10-31)
- Date: 2026-10-30

## Context

The project uses two declarative transformation tools: Lakeflow Declarative Pipelines and dbt Core. Both can create tables in Unity Catalog. If both are allowed to build any layer, the same business logic ends up implemented twice, lineage splits across two tools, and nobody can say which system is authoritative for a table.

## Decision

- The Lakeflow pipeline owns ingestion and cleansing: `retail_bronze` and `retail_silver`, including quarantine tables.
- dbt Core owns analytical modelling: `retail_gold`.
- dbt reads silver only through `source()` declarations. It never writes to bronze or silver. Lakeflow never publishes gold.

## Alternatives considered

| Option | Benefits | Drawbacks |
|---|---|---|
| Lakeflow for all layers (gold as materialized views) | One tool, one lineage graph, one run | Business SQL lives in pipeline code; weaker testing and documentation story than dbt; the case study would not demonstrate dbt |
| dbt for all layers | One tool, strong testing | dbt has no equivalent of Auto Loader checkpoints, expectations with quarantine metrics, or AUTO CDC sequencing; incremental ingestion of files would be hand-built |
| Split as decided | Each tool does what it is best at | Two tools to operate; the handoff between them (silver contract) must be explicit |

## Consequences

- The silver contract (C2 in `docs/data_contracts.md`) is the interface between the two tools and must be versioned.
- Orchestration must run the pipeline to completion before dbt (Phase 05).
- Lineage is split: pipeline lineage in Databricks, model lineage in dbt docs. Unity Catalog lineage may join the two views; verify in Phase 04.

## Verification required

- Table listing per schema after Phases 03 and 04 shows no cross-ownership.
