# Migration Narrative

The project's account of moving a nightly PySpark batch job to a Databricks Lakehouse, phase by phase. The account covers what was decided, what the recorded runs showed and what went wrong along the way. Each claim points to the phase HANDOFF that holds the evidence. All data is synthetic.

## 1. Starting point

A fictional Malaysian retailer runs one PySpark script every night. It reads every CSV extract ever delivered, joins customers, products, orders, items and payments, and overwrites three reports: daily sales, customer lifetime value and product performance.

Phase 02 built this job on purpose, with ten documented limitations (L1 to L10). Among them:
- **Ordering:** the last file read wins, whatever the record's own timestamp.
- **Replays:** replayed items and payments are counted twice.
- **Bad values:** they become nulls and vanish from totals.
- **Writes:** outputs are overwritten in place, with no previous version.

The limitations are deliberate. They are the behaviour a real migration starts from, and they become the differences the new platform must explain.

## 2. Target

| Layer | Tool | What it holds |
|---|---|---|
| Landing | Unity Catalog volume | Immutable CSV batches |
| Bronze | Lakeflow Declarative Pipelines, Auto Loader | Every row as received, as strings, with ingestion metadata |
| Silver and quarantine | Lakeflow expectations and AUTO CDC | Typed current state per key; failed rows kept with the rule they broke |
| Gold | dbt Core on the SQL warehouse | The three reports, as tested SQL models |
| Audit | Reconciliation job task | Every comparison of gold with the legacy outputs |

One rule shapes the design: each schema has exactly one writer (ADR 0001). Lakeflow never writes gold, and dbt never writes bronze or silver.

## 3. How it was built

**Phase 00, foundation.** The phase set out the architecture, the data contract framework, six decision records and the Free Edition assumptions to verify (`docs/platform_assumptions.md`). Every Free Edition capability was treated as unverified until a run confirmed it.

**Phase 01, synthetic data.** A deterministic generator produces an initial snapshot and daily change-feed batches, with late arrivals and replays built into the clean feed. Ten anomaly scenarios, one batch each, can be added on top. Every file and anomaly is listed in a manifest, and the true final state is written to `_expected/`. The same seed always gives byte-identical files, which makes every later comparison repeatable.

**Phase 02, the legacy job.** The phase wrote the reference job and its 20 baseline metrics. One finding came before any migration work (O1). On the anomalous data, the metrics computed from the same DataFrames disagreed with the written files on two daily counts, because Spark recomputed the lazy plan. The job now materialises each output once.

**Phase 03, bronze and silver.** The pipeline has five datasets per entity, running from bronze to silver and quarantine:
- bronze has an explicit all-string schema and rescued data
- silver uses AUTO CDC, sequenced by `source_updated_at` and `event_id`

The rules are generated from the data contract and mirror the Phase 01 validator. Updates were started while files were still arriving, so some steps could not be told apart. That is why every later runbook keeps landing changes and pipeline updates strictly in sequence.

**Phase 04, gold with dbt.** The phase added staging views and three mart tables in `retail_gold`, with 31 data tests and one business test per contract rule. The business date uses a fixed UTC+8 offset on epoch seconds, so the session time zone cannot shift it. Local setup failed once: dbt's dependencies did not yet build on Python 3.15. dbt now has its own Python 3.12 environment.

**Phase 05, orchestration and CI.** A bundle deploys the pipeline and the job `retail_nightly`: pipeline update, then `dbt build` (ADR 0007). GitHub Actions runs unit tests with Java, `dbt parse` with a placeholder profile and a token scan, all without secrets (ADR 0005).

**Phase 06, reconciliation and resilience.** A third job task compares gold with the legacy outputs key by key (ADR 0008). The phase also ran a resilience matrix:
- reruns and a replayed batch
- bad records, schema drift and late arrivals
- recovery from bad batches by full refresh
- gold rollback with `RESTORE`
- a deliberate failure

**Phase 07, benchmark and portfolio.** A small harness records runtimes from each system's own records (ADR 0009), and this document set presents the work.

## 4. What the evidence shows

From the Phase 06 HANDOFF, 2026-11-01:

- **Exact match on correct data.** In the clean state, gold equals the legacy job's output on the ordered dataset for every key and column of all three marts: 94, 530 and 50 rows, 0 differences.
- **Every difference explained on anomalous data.** Against the legacy output on the same anomalous feed, every differing key traces to a documented cause. Examples:
  - 22 daily keys
  - 26 customers
  - 15 products
  - the legacy null-date row, which has no counterpart in gold
- **The check can fail.** Run with the wrong dataset parameter, the reconciliation failed the job on exactly the 2 dates and 5 customers that the two silver-changing scenarios produce, and on nothing else.
- **Two implementations agree.** An independent SQL version of the comparison gave the same counts as the job task.
- **Resilience.** Each scenario of the test matrix was run and kept silver unchanged or restored it:
  - **reruns and replays:** silver counts and fingerprints unchanged
  - **late re-delivery of ten batches after a rebuild:** the same state as before
  - **removing the bad batches and running a full refresh:** silver equal to the generator's expected state
  - **gold:** `RESTORE` to an earlier version, then a rebuild forward

  Some of these results were reported by the maintainer as matching the runbook rather than pasted in full; the HANDOFF says which.
- **Runtime.** See `benchmarks/RESULTS.md`. Phase 02 measured the legacy job at 9.0 s on the small preset and 9.7 s on ten times the data. That shows start-up, not processing, dominating at this size.

## 5. What went wrong, and what changed because of it

| Phase | What happened | Change |
|---|---|---|
| 02 | Metrics from a recomputed lazy plan disagreed with the written files | Materialise once; a test compares the metrics with the files |
| 03 | Pipeline updates overlapped with file uploads | Runbooks separate landing changes from updates |
| 04 | dbt dependencies failed to build on Python 3.15 | A separate Python 3.12 environment for dbt, with pinned versions |
| 04 | dbt's anonymous `.user.yml` was committed | Removed and ignored |
| 06 | Spark skipped `_manifest.json`, because names starting with `_` count as hidden | The manifests are read with plain `open()`, with an end-to-end test |
| 06 | A serverless Python task reported `SystemExit: 0` as a failure | No `sys.exit`; failure is an exception |
| 06 | The platform ran a failed task a second time under the same run id, which duplicated the audit rows | Results are replaced per run id |
| 06 | Pipeline streaming tables refused time travel, so a past silver state could not be re-measured | Silver checks are taken while the state lasts; two steps were repeated to capture them |

None of these were visible from design documents. Each one surfaced because every step was run and its output compared with a prediction written beforehand.

## 6. What production would change

`docs/case_study.md` section 7 has the full table. In short:
- separate environments, and service principals instead of a personal login
- a schedule, retries chosen deliberately, and alerts on a failed reconciliation
- landing fed by the source system instead of manual uploads
- billing tables and budgets for cost
- integration tests against a test workspace before deployment
- a parallel-run period in which both systems are reconciled daily before the legacy job is switched off

See `docs/limitations.md` for what this project does not show.
