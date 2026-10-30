# 0004. Incremental ingestion, CDC upsert and quarantine

- Status: Proposed
- Date: 2026-10-30

## Context

The legacy job reloads everything on every run, double counts replays, and loses bad records without a trace. The source delivers an initial snapshot followed by incremental batches that contain inserts, updates, late arrivals, corrections and replays (Phase 01).

## Decision

1. **Bronze**: Auto Loader (`cloudFiles`) streaming tables, one per entity, reading CSVs from the landing volume. All business columns are stored as strings. Each row carries ingestion metadata (`_ingested_at`, `_source_file`, and Auto Loader's rescued data column). Bronze never rejects a row.
2. **Validation**: rules defined once as a mapping of rule name to SQL predicate over parsed values. Parsing uses `try_cast` and `try_to_timestamp` style functions so malformed values become null rather than failing the run.
3. **Silver**: AUTO CDC flow per entity, SCD type 1, keyed on the business key, sequenced by `source_updated_at` with a deterministic tie-breaker. Valid rows only (`expect_all_or_drop`).
4. **Quarantine**: an append-only `<entity>_quarantine` table per entity selecting the rows that fail any rule, with the failed rule names.
5. Referential integrity is flagged and tested downstream, not enforced as a silver rejection.

## Alternatives considered

| Option | Benefits | Drawbacks |
|---|---|---|
| Typed bronze (schema applied at read) | Earlier type errors, smaller storage | Malformed values fail parsing or become null before evidence is stored; bronze stops being a faithful copy |
| `MERGE` inside `foreachBatch` (hand-written CDC) | Works anywhere Structured Streaming runs | Ordering, late-arrival and tie handling must be hand-written and tested; no expectation metrics |
| `expect_or_drop` without a quarantine table | Simplest | Dropped rows are only counted, not kept; cannot be inspected or replayed |
| `expect_or_fail` on row rules | Strict | One bad row stops the whole pipeline |
| SCD type 2 in silver | Full history queryable | Extra complexity; legacy produces current state only, so reconciliation gains nothing; bronze already holds history |

## Consequences

- Re-running without new files is a no-op; replays cannot change silver (AC5).
- Every rejected row is inspectable with its reason (AC6).
- Rule definitions are shared between the expectation and the quarantine filter, so they cannot drift.
- Bronze storage grows with replays; acceptable at demo scale.

## Verification required

- Current Lakeflow Python API names (`pyspark.pipelines` versus `dlt`, `create_auto_cdc_flow` versus `apply_changes`) and AUTO CDC behaviour on equal sequence values (Phase 03).
- `cloudFiles.allowOverwrites` default and schema evolution mode behaviour for CSV (Phase 03).
