# 0002. Unity Catalog namespace and volume landing zone

- Status: Proposed
- Date: 2026-10-30

## Context

Unity Catalog uses a three-level namespace: catalog, schema, object. Free Edition provides a default catalog (assumed to be `workspace`, FE2) and may not permit creating additional catalogs (FE4). Source files need a governed landing location; external cloud storage is assumed unavailable (FE5).

## Decision

- Catalog: configurable through `RETAIL_CATALOG`, default `workspace`.
- Schemas: `retail_landing`, `retail_bronze`, `retail_silver`, `retail_gold`. The `retail_` prefix keeps the project's objects grouped and avoids collisions with anything else in a shared default catalog.
- Landing: a managed volume `retail_landing.raw`, addressed as `/Volumes/<catalog>/retail_landing/raw/`. Files uploaded there are immutable.
- Schemas are created once by `infra/sql/00_create_namespace.sql`, so ownership is explicit and pipelines or dbt do not depend on implicit schema creation.

## Alternatives considered

| Option | Benefits | Drawbacks |
|---|---|---|
| Dedicated catalog (for example `retail_migration`) with plain `bronze`, `silver`, `gold` schemas | Cleanest isolation; mirrors production catalog-per-domain patterns | May not be allowed on Free Edition; adds a setup step that can fail |
| Single schema with table prefixes | Works under the tightest permissions | Loses schema-level ownership and permissions; noisier names |
| DBFS root paths for landing | Familiar from older tutorials | Legacy pattern, not governed by Unity Catalog; discouraged on current workspaces |
| External location | Production-like | Assumed unavailable on Free Edition |

## Consequences

- Moving to a dedicated catalog later is a configuration change (`RETAIL_CATALOG`, `USE CATALOG` line, pipeline and dbt settings), not a redesign.
- If FE3 fails, fall back to prefixed tables in one schema and supersede this ADR.

## Verification required

- FE2, FE3, FE4 and FE5 in `docs/platform_assumptions.md`.
