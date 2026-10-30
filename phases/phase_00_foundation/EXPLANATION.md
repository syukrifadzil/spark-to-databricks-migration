# Phase 00 Explanation: Foundation

## 1. Objectives

Phase 00 settles the decisions every later phase depends on, so that no phase has to revisit them midway:

1. What problem the case study solves and how success is measured (goals and acceptance criteria).
2. The target architecture: layers, tools, ownership boundaries and data flow.
3. The contracts between layers and how bad data is handled.
4. Which platform capabilities are assumed, how each is verified, and what happens if one is missing.
5. Repository conventions: layout, naming, secrets handling, documentation structure.
6. A minimal, re-runnable workspace setup (schemas and a landing volume).

Phase 00 contains no data processing code. That is intentional: code written before the contracts and ownership are agreed tends to encode accidental decisions.

## 2. What Phase 00 deliberately does not do

- It does not create empty placeholder directories for later phases. Git does not track empty directories, and placeholder files go stale. Each phase creates its own directories; the target layout is documented in the README.
- It does not pin Python package versions. Pins belong with the code that imports the packages (Phase 01 and 02), after the maintainer reports what is installed locally.
- It does not create pipelines, jobs, warehouses or tokens in the workspace. It only verifies that they are available.

## 3. The case study in brief

A nightly PySpark job reads five CSV extracts (customers, products, orders, order items, payments), joins them and overwrites reporting outputs. It has no schema enforcement, no quality rules, no deduplication, no incremental behaviour and no reconciliation. The migration rebuilds it as a medallion Lakehouse on Databricks and then proves, with reconciliation on identical synthetic input, that the new platform produces the same business numbers on clean data and better-explained numbers on dirty data. Details: `docs/case_study.md`.

## 4. Architecture walkthrough

Read alongside the diagrams in `docs/architecture.md`.

### 4.1 Landing zone

The generator (Phase 01) writes CSV files locally. The maintainer uploads them into a Unity Catalog managed volume, `retail_landing.raw`, one folder per batch. A volume is a governed file location: it has Unity Catalog permissions and lineage, and is addressed with a path like `/Volumes/workspace/retail_landing/raw/initial/orders.csv`.

Files in the volume are treated as immutable. This is the foundation of recovery: if every file that was ever delivered is still there, any downstream table can be rebuilt from scratch.

### 4.2 Bronze

Bronze is a faithful copy of what was received. Auto Loader, Databricks' incremental file ingestion source, lists files in the volume, remembers in a checkpoint which ones it has already read, and appends only new rows. Each row is stored with all business columns as strings, plus metadata: when it was ingested, which file it came from, and any data that did not fit the expected columns (Auto Loader's rescued data column).

Why strings? If bronze applies types, a malformed timestamp either fails the read or silently becomes null before anything has been stored, and the evidence of the source problem is lost. Keeping strings means bronze can never reject data, and every quality decision happens in one place: silver.

### 4.3 Silver and quarantine

For each entity, silver parses the bronze strings into proper types using "try" functions that return null on failure instead of raising errors. A set of named rules (for example `order_id_not_null`, `amount_non_negative`, `order_date_parses`) is then evaluated.

- Rows that pass every rule flow into a change-data-capture (CDC) upsert. The upsert keys on the business key (such as `order_id`) and orders versions by `source_updated_at`, with a deterministic tie-breaker. The newest version wins. An older version arriving late cannot overwrite a newer one, and a replayed identical row changes nothing.
- Rows that fail any rule go to `<entity>_quarantine` together with the names of the rules they failed.

The rules are written once and used twice (as the expectation that filters valid rows, and negated to select quarantine rows), so the two paths cannot disagree.

Silver holds the current state of each entity (SCD type 1). History is still available in bronze.

### 4.4 Gold

dbt Core builds the business marts (daily sales, customer lifetime value, product performance) from silver tables, running SQL on a Databricks SQL warehouse. dbt brings version-controlled SQL, tests declared next to models, generated documentation and lineage.

### 4.5 Reconciliation

The legacy job and the Lakehouse process the same files. Phase 06 computes the same metrics on both sides (row counts, decimal sums, key sets, per-row hashes) and classifies each difference as a match, an explained difference (traceable to an injected anomaly and a contract rule), or an unexplained difference (a failure).

### 4.6 Orchestration and CI

The target is a Databricks job that runs the pipeline, then dbt, then reconciliation checks. If a feature is unavailable on Free Edition, the maintainer runs the same three steps by hand. GitHub Actions runs static checks and unit tests only and holds no workspace credentials.

## 5. Design decisions, alternatives and trade-offs

Each decision is recorded formally in `docs/adr/`. The reasoning is summarised here.

### D1. Lakeflow for bronze and silver, dbt for gold (ADR 0001)

Both tools can build tables. Letting both build any layer leads to duplicate logic and unclear authority. The split follows each tool's strengths: Lakeflow has incremental file ingestion, expectations with metrics and built-in CDC sequencing; dbt has the stronger testing, documentation and SQL modelling workflow.

- Alternative: Lakeflow for everything (gold as materialized views). Simpler to operate, one lineage graph, but business logic becomes pipeline code and the project no longer demonstrates dbt.
- Alternative: dbt for everything. dbt has no native file checkpointing or CDC sequencing; ingestion would be hand-built.
- Trade-off accepted: two tools to operate, with the silver contract as an explicit interface.

### D2. Default catalog with `retail_`-prefixed schemas (ADR 0002)

Free Edition provides a default catalog and may not allow new catalogs. Using `workspace` with prefixed schemas works under either condition. A dedicated catalog is cleaner but adds a setup step that might fail. Because the catalog name is configuration (`RETAIL_CATALOG`), switching later costs little.

### D3. Managed volume for landing (ADR 0002)

Volumes are governed by Unity Catalog and are the current recommended way to hold files. DBFS root paths are a legacy pattern. External locations would be production-like but are assumed unavailable on Free Edition.

### D4. Free Edition, serverless only (ADR 0003)

Free and reproducible by anyone, on the real platform. The cost is quotas, no SLA and possibly missing features. Every capability is listed in `docs/platform_assumptions.md` with a verification step and a fallback, and nothing in the design depends on Free Edition specifically.

### D5. String-typed bronze, typed silver (ADR 0004)

Covered in 4.2. The trade-off is that bronze is less convenient to query and uses more storage. At demo scale that is negligible, and the gain (no silent data loss at ingestion) is the central lesson of the migration.

### D6. AUTO CDC instead of hand-written MERGE (ADR 0004)

Hand-written `MERGE` inside `foreachBatch` works but requires writing and testing ordering, late-arrival and tie handling manually, and loses expectation metrics. Lakeflow's CDC flow handles sequencing declaratively. The exact API name has changed across releases (`apply_changes` to `create_auto_cdc_flow`), so Phase 03 must confirm it against current documentation.

### D7. Quarantine tables instead of drop-only or fail-fast expectations (ADR 0004)

`expect_or_drop` alone counts dropped rows but does not keep them, so they cannot be inspected or replayed. `expect_or_fail` stops the whole run for one bad row. Quarantine keeps the pipeline running and every rejected row inspectable.

### D8. Referential integrity is flagged, not rejected

An order can legitimately arrive before its customer record. Rejecting it in silver would lose valid data when the parent arrives later. Orphans are tested in dbt and reported in reconciliation instead.

### D9. SCD type 1 in silver

The legacy job produces current state only, so reconciliation needs current state. Bronze already holds the full history. SCD type 2 for customers is a documented optional extension.

### D10. Decimal money and explicit timezones (ADR 0006)

Floating point sums and implicit session timezones are the most common causes of reconciliation noise. `DECIMAL(18,2)`, half-up rounding, UTC source timestamps and an explicit `Asia/Kuala_Lumpur` business date allow clean-data reconciliation to demand exact equality.

### D11. CI without workspace credentials (ADR 0005)

Static checks and unit tests run safely on every pull request. Deployment remains a manual, observed action, consistent with the project rule that the maintainer runs everything. A gated deployment workflow is described as production hardening rather than built.

### D12. Workspace setup as a SQL file

`infra/sql/00_create_namespace.sql` creates the four schemas and the landing volume with `IF NOT EXISTS`, so it can be re-run safely. A SQL file was chosen over notebook cells or UI clicks because it is reviewable in git and identical on every run. Infrastructure-as-code tools (Terraform, bundles) were not used for this step: four statements do not justify another tool, and bundle support on Free Edition is unverified.

### D13. Diagrams as hand-written SVG

The first draft used Mermaid. After review, the diagrams were redrawn in a panelled card style: each environment or owner is a coloured panel, each component a card with an icon, title and two-line description, and arrows carry numbered steps explained in a caption. Mermaid cannot produce that layout.

- Alternative: draw.io or Excalidraw files exported to PNG. Easy to edit visually, but needs a separate tool, and the exported images are binary and do not diff in review.
- Alternative: keep Mermaid. Renders natively on GitHub and is quick to edit, but layout control is limited and the style requested is not achievable.
- Chosen: plain SVG files in `docs/diagrams/`, embedded as images. They are text, diff cleanly, need no tooling, and render on GitHub, including in dark mode, because each has an opaque white background. The trade-off is that moving a card means editing coordinates by hand.
- One legend is used everywhere: blue border for components built in this project (badge names the phase), orange for components that depend on something not yet verified, grey for platform services used as is. As phases complete and assumptions are verified, card colours and badges are updated.

### D14. Refunds and partial payments modelled explicitly

Decided during Phase 00 review. Orders may have several payments, and refunds are separate records. Amounts are always positive, and a type column carries the direction. That keeps "negative amount" an unambiguous data error and lets net paid, partial payment and partial refund states be derived in gold. Details are in `docs/data_contracts.md`.

## 6. File-by-file explanation

| File | Purpose | Key points |
|---|---|---|
| `README.md` | Project entry point | Replaces the prompt-pack README. States status honestly, shows the architecture and phase table, links all docs. |
| `.gitignore` | Keeps secrets and generated artefacts out of git | `.env` and variants (except `.env.example`), `profiles.yml`, `.databrickscfg`, virtual environments, Spark local metastore files, generated bulk data (`data/raw/`, `output/`), dbt build artefacts, bundle state, editor and OS files. |
| `.env.example` | Documents local configuration variables | Placeholders only. `DATABRICKS_TOKEN` is empty by default to encourage OAuth. Consumers arrive in Phase 04 onwards. |
| `infra/sql/00_create_namespace.sql` | Creates schemas and landing volume | Re-runnable. Single `USE CATALOG` line to change for a different catalog. Ends with two verification queries. |
| `docs/case_study.md` | Scenario, legacy problems, goals, non-goals, acceptance criteria, phase plan, demo versus production | Acceptance criteria name the evidence that proves them. |
| `docs/architecture.md` | Target architecture | Context, as-is versus to-be, layer ownership, naming, idempotency, quarantine, gold, environments, orchestration, reconciliation, security, recovery, open questions. |
| `docs/diagrams/*.svg` | Seven architecture diagrams | Hand-written SVG in one visual system: coloured panels per environment or owner, cards with icons, phase badges, numbered steps, a legend and a caption. See D13. |
| `docs/data_contracts.md` | Contract framework | Three contract boundaries, global CSV and type conventions, baseline entity contracts including refunds and partial payments, silver guarantees, anomaly-to-behaviour table, change process. |
| `docs/platform_assumptions.md` | Free Edition, cost, toolchain, responsibilities | Fifteen assumptions with verification steps, fallbacks and blank observation columns for the maintainer. |
| `docs/adr/README.md` | ADR index and template | |
| `docs/adr/0001` to `0006` | Decision records | Status "Proposed" until the maintainer accepts them. |
| `phases/phase_00_foundation/*.md` | This explanation, runbook, checklist, handoff | |

## 7. A single order's journey (illustrative, nothing executed)

1. The generator writes order `O-1` in the initial batch with `source_updated_at` T1. It writes the same order again in batch 2 with status `shipped` and T2, and replays the batch-2 row in batch 3.
2. The maintainer uploads each batch folder to the volume and runs the pipeline after each upload.
3. Bronze ends up with three rows for `O-1`, one per file, each with its source file path.
4. Silver: after batch 1, `O-1` exists with T1. After batch 2, the T2 version replaces it. After batch 3, the replayed T2 row has the same key and sequence, so silver is unchanged.
5. If batch 3 had contained a row for `O-1` with a malformed `order_date`, it would land in `orders_quarantine` with `order_date_parses` listed as the failed rule, and silver would be unaffected.
6. The legacy job, reading all three files without deduplication, would count `O-1` more than once. Reconciliation reports that difference as explained, citing the replay entry in the anomaly manifest.

The identifiers above are illustrative; real formats are defined in Phase 01.

## 8. Demo versus production

See the table in `docs/case_study.md` section 7. The main differences: separate environments, service principals instead of personal credentials, Unity Catalog grants, file-arrival triggers, alerting on quality thresholds, and measured cost.

## 9. Limitations and unverified items

- Free Edition items verified so far are recorded in `docs/platform_assumptions.md`. Pipeline and job creation (FE6, FE9) are confirmed only at API level; FE4, FE7, FE10, FE12 to FE14 remain untested.
- Lakeflow Python API names, AUTO CDC behaviour on equal sequence values, and the current bundle product name and syntax must be checked against current Databricks documentation before Phases 03 and 05.
- The SVG diagrams were written without being rendered. Text overflow or arrow placement errors only show once viewed.
