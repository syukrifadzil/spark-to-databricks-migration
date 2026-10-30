-- Creates the Unity Catalog schemas and the landing volume used by the project.
--
-- Where to run: Databricks SQL editor attached to a SQL warehouse, or a SQL
-- cell in a notebook on serverless compute.
-- Re-runnable: every statement uses IF NOT EXISTS.
-- Catalog: defaults to `workspace`. If you use another catalog, change the
-- USE CATALOG line below and RETAIL_CATALOG in your local .env.
-- Ownership: see docs/adr/0001 and docs/adr/0002.

USE CATALOG workspace;

CREATE SCHEMA IF NOT EXISTS retail_landing
  COMMENT 'Raw source files delivered to a managed volume. No tables.';

CREATE SCHEMA IF NOT EXISTS retail_bronze
  COMMENT 'Owned by the Lakeflow pipeline. Append-only raw Delta tables.';

CREATE SCHEMA IF NOT EXISTS retail_silver
  COMMENT 'Owned by the Lakeflow pipeline. Cleansed, deduplicated tables and quarantine tables.';

CREATE SCHEMA IF NOT EXISTS retail_gold
  COMMENT 'Owned by dbt Core. Analytical marts.';

CREATE VOLUME IF NOT EXISTS retail_landing.raw
  COMMENT 'CSV drops: initial snapshot and incremental batches. Files are immutable once uploaded.';

-- Verification. If the editor shows only the last result, run each line separately.
SHOW SCHEMAS LIKE 'retail_*';
SHOW VOLUMES IN retail_landing;
