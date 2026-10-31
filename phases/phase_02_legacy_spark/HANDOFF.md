# Phase 02 Handoff

## Status

Complete. Executed by the maintainer on 2026-10-31, Steps 1 to 8. All 34 tests passed and every run completed. On the anomalous dataset the written files reconciled fully with the code. The metrics JSON disagreed with those files on two daily order counts (O1, below), and the metrics path was fixed. On 2026-11-01 the maintainer reported the rerun after the fix and every remaining check as completed and verified. The individual outputs of those checks were not pasted into the conversation. Committed together with Phases 03 and 04.

## Decisions taken at the start of the phase

- Legacy input rule: the default proposed at the end of Phase 01. The maintainer approved Phase 02 ("Proceed") without choosing an alternative. Last file wins for customers, products and orders; items and payments stacked without deduplication.
- Mart business rules fixed in `docs/data_contracts.md` section 7, binding for Phase 04.

## Files created or changed

| File | Change |
|---|---|
| `legacy_spark/retail_nightly_job.py` | New: the legacy job |
| `legacy_spark/sql/baseline_metrics.sql` | New: 20 portable baseline metrics |
| `legacy_spark/__init__.py` | New, empty |
| `requirements-spark.txt` | New: `pyspark==4.3.0`, pinned after the first run to the version that produced the baseline |
| `tests/unit/test_legacy_job.py` | New: 4 tests, skipped without PySpark or Java |
| `docs/data_contracts.md` | Section 7: mart business rules (C3) |
| `docs/diagrams/legacy-job.svg` | New |
| `docs/diagrams/phase-plan.svg` | Phase 01 complete, Phase 02 in review |
| `.gitignore` | `.venv*/` |
| `README.md` | Status, phase table, layout, legacy quick start |
| `phases/phase_01_synthetic_data/HANDOFF.md` | Marked complete; commit hash not yet reported |
| `phases/phase_02_legacy_spark/*.md` | Explanation, runbook, checklist, this handoff |

## Confirmed by the recorded runs

- PySpark 4.3.0 installs and runs on Python 3.15.1 in `.venv`. The Python 3.12 fallback was not needed.
- The pattern `yyyy-MM-dd'T'HH:mm:ssX` parses the `Z` suffix: no null business dates on clean data.
- Non-ANSI casts return null for `12,50` and `abc`. The anomalous payment totals reconcile only if those amounts became null.

## Outstanding assumptions

- `coalesce(1)` after `orderBy` keeps the sort order in the written file. This matters only for readability; the tests do not depend on row order.

## Open items

**O1. Daily order counts on the anomalous dataset.** The code predicts:
- `daily_sales.orders_placed`: 5,310. That is the clean 5,300 plus the 10 new `ORD-X...` orders from invalid_reference.
- `daily_sales.orders_sold`: equal to `customer_lifetime_value.orders_sold`, 4,472. Every sold order has a known customer, and both outputs count the same set of sold orders.

The metrics JSON showed 5,308 and 4,469.

Diagnostics, run by the maintainer on 2026-10-31:
- **Null-date rows in the written file:** three rows, `,5,0,0,...`, `,0,4,0,...` and `,0,0,18,2982.55,...`. These are the orders, sold-orders and sold-lines aggregates, as section 5.1 of the explanation describes.
- **Sums of the written file:** placed 5,310 and sold 4,472. These match the prediction and the customer lifetime value output.
- **Clean against anomalous, by date:**
  - Five dates each lose one placed order, matching the five malformed_timestamp orders that move to the null row.
  - 2026-01-06 gains 10 orders and 50.00 in charges; 2026-01-08 gains 25.00.
  - The sold-order changes net to −5: −9 on dated rows, +4 on the null row.
  - Item and gross changes add up to the metrics: −21 items and −2,329.95 gross.
- **Rerun:** the metrics are identical to the first run, so the difference is deterministic.

**Conclusion.** The written outputs are correct. The metrics query is not. It runs `baseline_metrics.sql` over temporary views of the lazily evaluated DataFrames, so Spark recomputes the full plan with different, pruned columns. For `orders_placed` and `orders_sold` that recomputation returned other totals than the write did.

The exact Spark mechanism has not been identified. Gross sales, items, charges and row counts agreed, and only the counts derived from `orders` differed.

**Fix (verified by the maintainer, 2026-11-01).**
- `main` now materialises each output once with `localCheckpoint()`, so the files and the metrics come from the same rows.
- `test_job_completes_on_anomalous_input` now checks that the metrics equal the sums of the written daily file. It also checks that daily sold orders equal customer lifetime value sold orders.
- Whether the tiny anomalous sample would have reproduced O1 is unknown.

The commands that produced the diagnostics:

```bash
grep -E '^,' output/legacy/anomalous/daily_sales/part-*.csv
awk -F, 'NR>1 {p+=$2; s+=$3} END {print "placed", p, "sold", s}' output/legacy/anomalous/daily_sales/part-*.csv
diff <(sort output/legacy/clean/daily_sales/part-*.csv) <(sort output/legacy/anomalous/daily_sales/part-*.csv)
python -m legacy_spark.retail_nightly_job --input data/raw/anomalous --output output/legacy/anomalous_rerun
diff <(python -m json.tool --sort-keys output/legacy/anomalous/baseline_metrics.json | grep -v -e duration -e started) \
     <(python -m json.tool --sort-keys output/legacy/anomalous_rerun/baseline_metrics.json | grep -v -e duration -e started)
```

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Predicted anomalous behaviour wrong | Section 5 of the explanation misleads Phase 06 | Observed results recorded in section 5; O1 resolved |
| Recomputing the same Spark plan gives different totals elsewhere too (O1) | Phase 06 compares against metrics that differ from the files | Outputs materialised once; metrics checked against the files in the test; Phase 06 reads the written files |
| Business rules in section 7 later found unsuitable | Both legacy job and dbt must change | Agree them now (checklist) |

## Human outputs required

All measured on the maintainer's Mac on 2026-10-31.

- Java version (Step 1): none at first (`Unable to locate a Java Runtime`). After `brew install openjdk@17`: OpenJDK 17.0.21.0.3 (Homebrew), with `JAVA_HOME` and `PATH` added to `~/.zshrc`.
- PySpark version and Python environment used (Step 2): PySpark 4.3.0 with py4j 0.10.9.9, on Python 3.15.1 in `.venv`. pip built it from the source distribution (455.9 MB).
- Smoke test result (Step 3): `rows: 3`. Warnings: loopback hostname, native-hadoop, `jdk.incubator.vector`. All harmless.
- `pytest -q` summary (Step 4): `34 passed in 14.76s`.
- Samples run (Step 5): read 54 customers, 19 products, 123 orders, 174 items and 94 payments from 4 files each. Duration 7.5 s on the second run; the first was 8.8 s.
  - Rows: customer lifetime value 49, product performance 15, daily sales 30.
  - Null-date rows: 0.
  - Gross sales: 17889.26 in all three outputs.
  - Charges 18255.21, refunds 500.99, net payments 17754.22.
  - Dates 2025-12-02 to 2026-01-04.
- Small and medium (Step 6), Spark 4.3.0:

  | Metric | Small (`data/raw/clean`) | Medium |
  |---|---|---|
  | `time` total | 9.554 s | 10.128 s |
  | `duration_seconds` | 9.0 | 9.7 |
  | Rows read: customers / products / orders / items / payments | 548 / 55 / 5,942 / 10,890 / 5,904 | 5,334 / 539 / 59,505 / 109,149 / 59,248 |
  | `daily_sales.rows` | 94 | 94 |
  | `daily_sales.first_date` / `last_date` | 2025-10-03 / 2026-01-04 | 2025-10-03 / 2026-01-04 |
  | `daily_sales.orders_placed` | 5,300 | 53,000 |
  | `daily_sales.orders_sold` | 4,477 | 44,977 |
  | `daily_sales.items_sold` | 16,242 | 160,517 |
  | `daily_sales.gross_sales` | 2,646,985.28 | 23,138,850.62 |
  | `daily_sales.charges` | 2,780,817.81 | 24,271,908.63 |
  | `daily_sales.refunds` | 146,764.64 | 1,303,253.89 |
  | `daily_sales.net_payments` | 2,634,053.17 | 22,968,654.74 |
  | `daily_sales.null_business_date_rows` | 0 | 0 |
  | `customer_lifetime_value.rows` | 530 | 5,150 |
  | `customer_lifetime_value.customers_with_sales` | 510 | 5,025 |
  | `customer_lifetime_value.orders_sold` | 4,477 | 44,977 |
  | `customer_lifetime_value.lifetime_gross_sales` | 2,646,985.28 | 23,138,850.62 |
  | `customer_lifetime_value.lifetime_net_paid` | 2,634,053.17 | 22,968,654.74 |
  | `product_performance.rows` | 50 | 500 |
  | `product_performance.products_sold` | 46 | 454 |
  | `product_performance.units_sold` | 16,242 | 160,517 |
  | `product_performance.gross_sales` | 2,646,985.28 | 23,138,850.62 |

  Notes on these runs:
  - Medium takes about the same time as small despite ten times the rows. JVM and Spark start-up dominate at these sizes, so these timings say nothing about scaling.
  - zsh `time` reported only 0.12 to 0.14 s of user CPU, which does not seem to include the JVM's work. Use the total.
  - On small, 5 more items and 3 more payments were read than the expected final state (10,885 and 5,901). Those are replays, and the legacy job counts them twice (L4). Phase 06 measures their effect on the totals.
- Anomalous comparison (Step 7): the job completed. 15 of 20 metrics differ from clean. Section 5 of `EXPLANATION.md` has the reconciliation by scenario. Every payment difference is explained to the cent. Two daily order counts are open (O1).
- Optional ordered dataset run (Step 8):
  - Generator: final state 530 / 50 / 5,300 / 10,885 / 5,901; 0 late arrivals, 0 replays, 5 corrections.
  - Validator: PASS.
  - Job: completed in 8.5 s. It read exactly 10,885 items and 5,901 payments, so nothing was double counted.
  - Metrics were not printed. They are in `output/legacy/ordered/baseline_metrics.json`.
- O1 diagnostics output: recorded under O1 above.
- After the O1 fix: `pytest -q` in `.venv` gave `40 passed in 12.74s` on 2026-10-31. That total includes the Phase 03 and 04 tests. The anomalous rerun was reported verified on 2026-11-01; its metrics were not pasted.
- Commit (Step 9): committed together with Phases 03 and 04 on 2026-11-01; see `git log`.
- Any failures, with the full output: none. Two command typos were corrected and rerun: a missing `/` in a `cat` path, and a trailing `/` on `--output`, which only doubles the slash in the log line.

## Phase 03 prerequisites

1. Phase 02 completed and committed, with O1 resolved.
2. The Databricks CLI still authenticates (`databricks current-user me`).
3. The Lakeflow API names must be checked against current Databricks documentation before any code is written: the Python module (`pyspark.pipelines` or `dlt`), `create_auto_cdc_flow`, the expectation decorators and Auto Loader options. Phase 03 starts with that check and lists anything it cannot confirm.
4. Decide which dataset to upload first. Suggested: `data/raw/clean` (small), then `data/raw/anomalous`.
5. Explicit approval to start Phase 03.
