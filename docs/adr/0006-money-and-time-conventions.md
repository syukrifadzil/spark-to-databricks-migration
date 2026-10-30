# 0006. Monetary precision and timezone conventions

- Status: Accepted (2026-10-31)
- Date: 2026-10-30

## Context

Reconciliation compares legacy and modern totals exactly. Floating point arithmetic, inconsistent rounding modes and implicit session timezones are the usual causes of totals that differ by a few cents or orders that land on different days.

## Decision

- Money is MYR, stored as `DECIMAL(18,2)` in silver and gold and written as plain two-decimal text in CSV. Floating point types are never used for money, including in the legacy job's final outputs.
- Rounding is half-up at two decimals. Spark `round()` is half-up; Python's `decimal` module defaults to half-even, so the generator sets `ROUND_HALF_UP` explicitly.
- Source timestamps are UTC (ISO 8601 with `Z`). The business date for daily reporting is the date in `Asia/Kuala_Lumpur` (UTC+8, no daylight saving).
- Every Spark session that computes dates sets `spark.sql.session.timeZone` explicitly rather than relying on the machine default.

## Alternatives considered

| Option | Benefits | Drawbacks |
|---|---|---|
| `DOUBLE` for amounts | Simpler CSV inference | Non-exact sums; reconciliation noise |
| Store integer sen (cents) | Exact, simple arithmetic | Less readable; every consumer must divide by 100 |
| Local time in source files | Matches business view | Ambiguous without offset; harder to compare across systems |

## Consequences

- Clean-data reconciliation can require exact equality, not tolerances.
- The legacy job (Phase 02) must cast amounts to decimal before aggregating, or the documented difference must be explained in reconciliation.

## Verification required

- Phase 01 confirms timestamp format and rounding in the generator; Phase 02 and 03 confirm the session timezone setting.
