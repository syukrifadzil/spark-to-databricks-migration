# Architecture Decision Records

Each record captures one decision: the context, the choice, the alternatives considered and the consequences. Records are not edited after acceptance except for status; a changed decision gets a new record that supersedes the old one.

Status values: Proposed, Accepted, Superseded by NNNN, Rejected.

| ADR | Title | Status |
|---|---|---|
| [0001](0001-layer-ownership.md) | Lakeflow owns bronze and silver; dbt owns gold | Accepted |
| [0002](0002-unity-catalog-namespace.md) | Unity Catalog namespace and volume landing zone | Accepted |
| [0003](0003-free-edition-serverless-target.md) | Target Databricks Free Edition on serverless compute | Accepted |
| [0004](0004-incremental-ingestion-and-quarantine.md) | Incremental ingestion, CDC upsert and quarantine | Accepted |
| [0005](0005-human-operated-execution-and-ci-scope.md) | Human-operated deployment; CI limited to static checks and unit tests | Accepted |
| [0006](0006-money-and-time-conventions.md) | Monetary precision and timezone conventions | Accepted |
| [0007](0007-orchestration-as-a-bundle-job.md) | One bundle-deployed job runs the pipeline, dbt and reconciliation | Accepted |
| [0008](0008-reconcile-key-by-key-against-legacy.md) | Reconcile gold with the legacy outputs key by key, and explain differences by cause | Accepted |
| [0009](0009-benchmark-with-measured-proxies-only.md) | Benchmark with measured wall-clock proxies only, and no speed comparison | Proposed |

## Template

```markdown
# NNNN. Title

- Status: Proposed
- Date: YYYY-MM-DD

## Context
## Decision
## Alternatives considered
## Consequences
## Verification required
```
