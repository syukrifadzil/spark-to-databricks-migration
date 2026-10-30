# Phase 01 — Synthetic Data Generation and Data Contracts

## Context and prerequisites
You are the lead Data Engineer and Solution Architect for the Legacy Spark to Databricks Lakehouse Migration Case Study. The migration covers PySpark, Delta Lake, Lakeflow Declarative Pipelines (formerly DLT), Unity Catalog, dbt Core, Databricks Jobs and GitHub Actions. Target Databricks Free Edition where feasible; document feature limitations rather than assuming enterprise capabilities.

Before writing, read `GLOBAL_MASTER_INSTRUCTIONS.md`, Phase 00 architecture, repository conventions, and any existing Phase 01 work. Preserve existing work and avoid duplicate implementations.

## Non-negotiable execution boundary
You may READ project files and WRITE source code, tests, configs and documentation only. Do not run shell commands, Python, Spark, SQL, notebooks, tests, linters, package installations, cloud connections, Git commands, or dataset generation. Do not run environment inspection commands. All execution and Git actions belong to the human operator. Never claim tests passed or datasets were produced without user-supplied evidence. Stop after this phase for manual review.

## Objective
Implement a reproducible, configurable synthetic Malaysian retail transaction data framework. Use Python, Faker, NumPy and Pandas where useful; avoid unnecessary dependencies. The generator creates CSVs only when the human runs it. All records must be fictional. Use MYR and document monetary precision and rounding.

## Baseline datasets and contracts
Create relational datasets with configurable default counts:
- `customers.csv`: 5,000 customer profiles (customer_id, synthetic name/email, region, created_at, updated_at).
- `products.csv`: 500 products (product_id, category, price, status).
- `orders.csv`: 50,000 orders (order_id, customer_id, order_date, status, source_updated_at).
- `order_items.csv`: approximately 100,000 items (order_item_id, order_id, product_id, quantity, unit_price).
- `payments.csv`: approximately 50,000 payment records (payment_id, order_id, amount, method, status).

Define primary and foreign keys, nullability, allowed values, CSV encoding, date/time conventions, timezone, decimals, and business rules. The clean baseline must satisfy the declared contracts, including order item totals and payment reconciliation rules. Explain how refunds, failed payments and partial payments are treated if modeled.

## Deterministic generation
Support CLI-configurable row counts, output path, fixed random seed, fixed as-of date, and batch sizes. Keep identifiers stable, outputs reproducible and reference integrity intact. Avoid implicit dependence on the current date or locale. Implement small and medium presets and clearly state exact counts versus approximate counts.

## Incremental simulation
Generate an initial snapshot and at least three subsequent batches. Include new customers, new orders/items/payments, customer updates, order status updates, late arrivals, source corrections and replayed events. Distinguish inserts, updates, corrections, and duplicates. Design stable event IDs, source_updated_at, event timestamps, batch IDs, and deterministic ordering. Specify whether each file is a snapshot, CDC-style change feed, or append-only event feed, and how future Lakeflow ingestion should interpret it. Make idempotent processing testable.

## Anomaly injection
Implement independently configurable anomaly scenarios, kept separate from clean baseline outputs: duplicate transaction IDs, null required values, invalid customer/product references, negative amounts, order/payment mismatches, malformed types/timestamps, schema evolution, late arrivals and replays. Produce a machine-readable anomaly manifest with affected keys, scenario, expected validation behavior, and counts. Ensure tests can isolate each scenario and avoid unintended anomalies.

## Validation and tests (author only; do not run)
Write schema and business-rule validators covering row counts, uniqueness, mandatory fields, referential integrity, monetary calculations, timestamp validity, expected anomaly counts and deterministic generation. Return meaningful diagnostics and nonzero exit status on validation failures. Add pytest unit tests for configuration errors, reproducibility, row counts, foreign keys, monetary arithmetic, incremental semantics, duplicate detection and anomaly injection. Distinguish structural checks from business checks.

## Repository layout
Keep production code in canonical locations and phase explanations in the phase folder. Prefer this structure, adapting to Phase 00 if needed:
```
data/
  generators/generate.py
  generators/generate_batches.py
  generators/inject_anomalies.py
  generators/validate.py
  contracts/
  samples/
  raw/initial/
  raw/incremental/
  fixtures/duplicates/
  fixtures/invalid_records/
  fixtures/schema_evolution/
tests/unit/test_data_generation.py
phases/phase_01_synthetic_data/
  PROMPT.md
  EXPLANATION.md
  MANUAL_RUNBOOK.md
  VALIDATION_CHECKLIST.md
  HANDOFF.md
```
Only commit small reproducible sample data; ignore generated bulk CSVs, secrets, local config, venvs and caches.

## Teaching and documentation requirements
Explain every dataset and relationship, generator design, random seeds, distributions, each important function (arguments, returns, failure conditions), batch semantics, anomaly logic, data contracts, and tradeoffs. Explain how these files feed legacy Spark and future Databricks Bronze/Silver processing and support reconciliation and benchmarking. Use natural, technically accurate, human-written engineering prose. No AI attribution, `Co-Authored-By` trailers, emojis, generated-by notices or unsupported success claims.

Populate the following files with substantive phase-specific content:
1. `EXPLANATION.md`: step-by-step architecture, design choices, code walkthrough, diagrams where useful.
2. `MANUAL_RUNBOOK.md`: exact macOS setup, dependency installation, generation, batch creation, anomaly injection, validation, test commands, expected outputs/counts, troubleshooting, and cleanup. Every command must match the files and CLI arguments actually authored. Clearly flag destructive commands.
3. `VALIDATION_CHECKLIST.md`: manual checkboxes for correctness, reproducibility, anomaly expectations, tests and acceptance criteria.
4. `HANDOFF.md`: created/changed files, outstanding assumptions, limitations, untested status, human outputs required and Phase 02 prerequisites.
5. Update relevant README, dependencies, data dictionary and `.gitignore` as needed.

## GitHub handoff
Provide manual `git status`, `git diff`, selective `git add`, `git commit -m "feat(data): implement reproducible retail data generator"`, and `git push` instructions. Do not run them. Explain how to check staged files for secrets and generated data. Do not add AI co-author attribution.

## Completion gate
At the end, summarize what was authored versus what remains unverified. Provide the exact manual execution sequence, expected artifacts and errors to watch for. Wait for my actual execution and validation results before starting Phase 02.
