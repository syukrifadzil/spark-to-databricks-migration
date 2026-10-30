# 0003. Target Databricks Free Edition on serverless compute

- Status: Accepted (2026-10-31)
- Date: 2026-10-30

## Context

The project is a public portfolio piece that anyone should be able to reproduce without a paid cloud account. Databricks Free Edition offers a no-cost workspace with serverless compute and Unity Catalog, but with quotas and feature restrictions that are not guaranteed to stay stable.

## Decision

- Target Free Edition and serverless compute only. No cluster configuration appears in pipeline, job or bundle definitions.
- Treat every Free Edition capability as an assumption with a recorded verification and a fallback (`docs/platform_assumptions.md`).
- Keep the design portable to a paid workspace: nothing depends on Free Edition specifically, only on features that also exist in paid tiers.

## Alternatives considered

| Option | Benefits | Drawbacks |
|---|---|---|
| Paid trial workspace on a cloud provider | Full feature set, real cost data | Time-limited, needs a cloud account and billing, harder for readers to reproduce |
| Local only (open-source Spark and Delta) | Fully offline | Cannot demonstrate Lakeflow, Unity Catalog or SQL warehouses, which are the point of the migration |
| Free Edition (chosen) | Free, reproducible, real platform | Quotas, no SLA, some features possibly missing |

## Consequences

- Data volumes are kept small enough to fit quotas (small and medium presets in Phase 01).
- Performance numbers from Free Edition are not representative of production and are labelled as such.
- Some orchestration and deployment features may require manual fallbacks.

## Verification required

- All FE items in `docs/platform_assumptions.md`.
