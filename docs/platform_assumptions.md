# Platform, Cost and Environment Assumptions

Databricks Free Edition features and quotas change over time and are not fully documented in one place. Every item below is an assumption until the maintainer records an observation in the "Observed" column. Later phases must not depend on an item marked unverified without using its fallback.

## 1. Databricks Free Edition assumptions

| ID | Assumption | Why it matters | How to verify | Fallback if false | Observed | Date |
|---|---|---|---|---|---|---|
| FE1 | Compute is serverless only; classic clusters cannot be created. | Pipeline and job configs must not specify cluster settings. | Compute page: check whether creating an all-purpose cluster is offered. | None needed; design is serverless already. | `databricks clusters list` returned no clusters and no error. Whether creation is offered was not checked; no impact on the design. | 2026-10-31 |
| FE2 | Unity Catalog is enabled with a default catalog named `workspace`. | Namespace in ADR 0002. | Catalog explorer, or `SHOW CATALOGS;` in the SQL editor. | Use whatever catalog exists; set `RETAIL_CATALOG` and the `USE CATALOG` line accordingly. | Confirmed via `databricks catalogs list`: `workspace` is a managed catalog; `system` and `samples` also present. | 2026-10-31 |
| FE3 | The user can create schemas and managed volumes in that catalog. | Landing and layer schemas. | Run `infra/sql/00_create_namespace.sql`. | Use the existing `default` schema with `retail_` table prefixes. | Confirmed: `infra/sql/00_create_namespace.sql` created the four `retail_*` schemas and the managed volume `retail_landing.raw`, verified with `databricks schemas list` and `databricks volumes list`. | 2026-10-31 |
| FE4 | Creating a new catalog may not be permitted. | Decides whether a dedicated catalog is an option. | Optional probe in the Phase 00 runbook. | Stay on `workspace` (the baseline design). | Not probed. A second managed catalog exists (created by a Databricks tutorial), which suggests creation is possible; the user is in the workspace `admins` group. | 2026-10-31 |
| FE5 | External locations and storage credentials for your own cloud storage are not available. | Landing must use a managed volume. | Catalog explorer: external data section. | None needed; design uses managed volumes. | `databricks external-locations list` shows only the Databricks-managed storage location. Creating one was not attempted; no impact on the design. | 2026-10-31 |
| FE6 | Lakeflow Declarative Pipelines can be created and run on serverless compute. | Phase 03 depends on it. | Jobs and Pipelines page: create option for an ETL pipeline is offered (do not create yet). | Plain notebooks with Structured Streaming and `MERGE` (loses expectations and event log). | `databricks pipelines list-pipelines` returned an empty list with no error, so the API is available. Creating and running a pipeline is first tested in Phase 03. | 2026-10-31 |
| FE7 | One pipeline can publish tables to more than one schema using fully qualified names. | Separate bronze and silver schemas. | Phase 03 test. | Single schema for both layers with `bronze_` and `silver_` prefixes. | | |
| FE8 | A serverless SQL warehouse is available (possibly one, of a fixed small size). | dbt connection target. | SQL Warehouses page; note name and HTTP path. | Run dbt models through a Databricks job dbt task or notebook, if available. | Confirmed: one warehouse, "Serverless Starter Warehouse", size 2X-Small (stopped when checked). | 2026-10-31 |
| FE9 | Jobs can be created, with limits on concurrency and tasks. | Phase 05 orchestration. | Jobs and Pipelines page. | Manual step-by-step runs. | `databricks jobs list` returned no jobs and no error, so the API is available. Limits not yet known. | 2026-10-31 |
| FE10 | The dbt task type is available in jobs. | Phase 05 orchestration of gold. | Phase 05 check. | Run dbt locally after the pipeline. | | |
| FE11 | OAuth login from the Databricks CLI works; personal access tokens may or may not be available. | Local CLI, dbt authentication. | `databricks auth login`; user settings, developer section. | Whichever method is available; never commit either. | OAuth login succeeded; profile listed as valid. `databricks tokens list` returned an empty list with no error, so the token API is reachable; creating a token was not attempted. | 2026-10-31 |
| FE12 | Bundle deployment works against Free Edition. | Phase 05 infrastructure as code. | Phase 05 `bundle validate` then `bundle deploy`. | Create job and pipeline in the UI from documented settings; keep bundle files as documentation. | | |
| FE13 | Daily or periodic compute quotas exist and can stop work until reset. | Run sizes and benchmark planning. | Free Edition documentation and any usage page in the workspace. | Use the small data preset; spread runs across days. | | |
| FE14 | Outbound internet from serverless compute may be restricted. | Installing extra Python libraries inside the pipeline. | Phase 03, only if a library is needed. | Keep pipeline code to built-in libraries. | | |
| FE15 | Free Edition is for non-commercial use and carries no SLA. | Portfolio wording. | Free Edition terms. | Not applicable; state it in the README. | | |

## 2. Cost assumptions

- Free Edition has no billing, so cost cannot be measured in currency. Phase 07 will record resource proxies instead (wall-clock runtime, rows processed, number of pipeline updates), labelled as Free Edition measurements.
- No cost figures, DBU rates or price comparisons will be published unless the maintainer measures them on a paid workspace and records the source.
- Design choices that would reduce cost in production (incremental ingestion instead of full reloads, serverless auto-stop, table-level rebuild only where needed) are described qualitatively, not quantified.

## 3. Local toolchain

Versions are deliberately not pinned in Phase 00. Phase 01 and 02 pin Python packages after the maintainer reports what is installed.

| Tool | Needed from | Purpose | Guidance |
|---|---|---|---|
| macOS terminal (zsh) | 00 | All commands | |
| Homebrew | 00 | Installing CLI tools | |
| Git | 00 | Version control | Any recent version; `git init -b` needs 2.28 or later |
| Python 3 | 01 | Generator, tests, legacy job, dbt | 3.11 is a conservative choice for compatibility across PySpark and dbt-databricks; confirm against the versions pinned in Phase 01 |
| Java JDK | 02 | Local PySpark | Java 17 is supported by current PySpark releases; confirm against the PySpark version pinned in Phase 02 |
| Databricks CLI | 00 (optional), 03 | Volume uploads, auth, bundles | The current CLI installed from the `databricks/tap` Homebrew tap, not the legacy `databricks-cli` pip package |
| dbt Core with dbt-databricks | 04 | Gold marts | Installed into the project virtual environment |

## 4. Responsibilities by environment

| Environment | Holds | Must never hold |
|---|---|---|
| Local workstation | Source code, virtual environment, generated CSVs, legacy outputs, `.env`, `~/.databrickscfg` | Nothing restricted beyond normal care; secrets stay out of the repository directory's tracked files |
| Databricks workspace | Volume files, Delta tables, pipeline, warehouse, jobs | Hard-coded credentials in notebooks or pipeline code |
| GitHub repository | Code, configs with placeholders, docs, small samples | `.env`, tokens, workspace URLs paired with credentials, bulk generated data |
| GitHub Actions | Static checks and unit tests | Workspace credentials (baseline design) |
