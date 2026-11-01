"""Legacy versus Lakehouse reconciliation of the three reporting marts.

Each gold mart is compared with a legacy job output for the same input, key by key:
row counts, column totals, duplicate keys, keys missing on either side, and a hash of every
row. A difference is explained only when its key is touched by an allowed cause:
- a late arrival or replay listed in the clean feed manifest (the legacy job applies those by
  file order, or counts them twice)
- a row in an anomaly scenario batch (_anomaly_manifest.json)
Every other difference is unexplained, and any unexplained difference fails the run.

Runs as the reconciliation task of the retail_nightly job (databricks.yml), and locally with
the legacy outputs on both sides as a rehearsal. See
phases/phase_06_reconciliation_resilience/EXPLANATION.md.

    python -m reconciliation.reconcile --dataset clean --landing data/raw/clean \\
        --legacy-root output/legacy --modern-csv output/legacy/ordered
"""
import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from functools import reduce

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

MONEY = "decimal(18,2)"
NUMERIC = ("bigint", MONEY)
# mart: (key, {column: type}), in the column order the legacy job writes and dbt builds.
MARTS = {
    "daily_sales": ("business_date", {
        "business_date": "date", "orders_placed": "bigint", "orders_sold": "bigint", "items_sold": "bigint",
        "gross_sales": MONEY, "charges": MONEY, "refunds": MONEY, "net_payments": MONEY}),
    "customer_lifetime_value": ("customer_id", {
        "customer_id": "string", "region": "string", "first_order_date": "date", "last_order_date": "date",
        "orders_sold": "bigint", "lifetime_gross_sales": MONEY, "lifetime_net_paid": MONEY}),
    "product_performance": ("product_id", {
        "product_id": "string", "product_name": "string", "category": "string", "status": "string",
        "units_sold": "bigint", "gross_sales": MONEY, "orders_sold": "bigint"}),
}
# For each dataset in the workspace: which legacy output to compare with, and which causes may
# explain a difference. "ordered" has no late arrivals or replays, so the legacy job gets it
# right and the comparison is exact (Phase 02 EXPLANATION section 5).
PLANS = {
    "clean": [("ordered", ()), ("clean", ("feed",))],
    "anomalous": [("ordered", ("silver_anomaly",)), ("anomalous", ("feed", "anomaly"))],
}
PRIMARY_KEYS = {"customers": "customer_id", "products": "product_id", "orders": "order_id",
                "order_items": "order_item_id", "payments": "payment_id"}
TS_FORMAT = "yyyy-MM-dd'T'HH:mm:ssX"
SEED_SCHEMA = "cause STRING, entity STRING, key STRING"
SUMMARY_SCHEMA = ("run_id STRING, run_at TIMESTAMP, dataset STRING, legacy_dataset STRING, causes STRING, "
                  "mart STRING, legacy_rows BIGINT, modern_rows BIGINT, legacy_duplicate_keys BIGINT, "
                  "modern_duplicate_keys BIGINT, missing_in_modern BIGINT, missing_in_legacy BIGINT, "
                  "value_mismatches BIGINT, explained BIGINT, unexplained BIGINT, totals STRING, status STRING")
DIFF_SCHEMA = ("run_id STRING, dataset STRING, legacy_dataset STRING, mart STRING, key STRING, kind STRING, "
               "columns STRING, legacy_values STRING, modern_values STRING, causes STRING, explained BOOLEAN")


def business_date(column):
    """Kuala Lumpur date of a UTC timestamp string, null when it does not parse.
    Same arithmetic as dbt/macros/business_date.sql, so it ignores the session time zone."""
    seconds = F.unix_seconds(F.try_to_timestamp(F.col(column), F.lit(TS_FORMAT)))
    return F.date_from_unix_date(F.floor((seconds + 28800) / 86400).cast("int"))


def read_json(path):
    # Plain open(), not Spark: Spark's file listing skips names that start with "_" (as it does
    # _SUCCESS), so it reads nothing for _manifest.json. Volumes are /Volumes/... POSIX paths.
    with open(path) as f:
        return json.load(f)


def read_csv_mart(spark, folder, mart):
    """A mart in the legacy job's CSV layout (<folder>/<mart>/part-*.csv), typed."""
    _, columns = MARTS[mart]
    raw = spark.read.option("header", True).csv(f"{folder}/{mart}")
    return raw.select(*[F.col(c).cast(t).alias(c) for c, t in columns.items()])


def read_table_mart(spark, schema, mart):
    _, columns = MARTS[mart]
    return spark.table(f"{schema}.mart_{mart}").select(*[F.col(c).cast(t).alias(c) for c, t in columns.items()])


# --- causes ------------------------------------------------------------------------------

def feed_seeds(spark, manifest):
    """Late arrivals and replays in the clean feed, from _manifest.json."""
    rows = ([("feed:late_arrival", r["entity"], r["key"]) for r in manifest["late_arrivals"]]
            + [("feed:replay", r["entity"], r["key"]) for r in manifest["replays"]])
    return spark.createDataFrame(rows, SEED_SCHEMA)


def anomaly_seeds(spark, landing, manifest, silver_only=False):
    """Every row of each anomaly scenario's batch, by primary key. With silver_only, only the
    scenarios the manifest says change silver, which are the only ones allowed to move gold."""
    changes_silver = {e["scenario"] for e in manifest["entries"] if e["silver_effect"] != "none"}
    frames = []
    for batch, meta in sorted(manifest["batches"].items()):
        if silver_only and meta["scenario"] not in changes_silver:
            continue
        for file in meta["files"]:
            entity = file[:-len(".csv")]
            rows = spark.read.option("header", True).csv(f"{landing}/{batch}/{file}")
            frames.append(rows.select(F.lit(f"anomaly:{meta['scenario']}").alias("cause"),
                                      F.lit(entity).alias("entity"),
                                      F.col(PRIMARY_KEYS[entity]).alias("key")))
    return reduce(DataFrame.unionByName, frames, spark.createDataFrame([], SEED_SCHEMA))


def touched_keys(spark, landing, seeds):
    """The mart keys each cause can change, as {mart: DataFrame(key, cause)}.

    A seed names a source record. Every version of it in the landing files counts, so a bad
    version and the good one it replaces are both covered:
    - an order touches its order dates, its customer and the products on its items
    - an item touches its order's dates and customer, and its own product
    - a payment touches its payment date and its order's customer
    - a customer or product touches its own key, which may be null
    """
    def read(entity, *columns):
        return spark.read.option("header", True).csv(f"{landing}/batch_*/{entity}.csv").select(*columns)

    orders = read("orders", "order_id", "customer_id", "order_date").withColumn("order_bd", business_date("order_date"))
    items = read("order_items", "order_item_id", "order_id", "product_id")
    payments = read("payments", "payment_id", "order_id", "payment_at").withColumn("payment_bd", business_date("payment_at"))

    def seeded(entity):
        return seeds.filter(F.col("entity") == entity).select("cause", "key")

    order_seeds = seeded("orders").select("cause", F.col("key").alias("order_id"))
    item_rows = seeded("order_items").join(items, F.col("key") == F.col("order_item_id"))
    payment_rows = seeded("payments").join(payments, F.col("key") == F.col("payment_id"))
    dated_orders = order_seeds.unionByName(item_rows.select("cause", "order_id"))
    any_orders = dated_orders.unionByName(payment_rows.select("cause", "order_id"))

    daily = (dated_orders.join(orders, "order_id").select("cause", F.col("order_bd").alias("key"))
             .unionByName(payment_rows.select("cause", F.col("payment_bd").alias("key"))))
    customers = (seeded("customers")
                 .unionByName(any_orders.join(orders, "order_id").select("cause", F.col("customer_id").alias("key"))))
    products = (seeded("products")
                .unionByName(order_seeds.join(items, "order_id").select("cause", F.col("product_id").alias("key")))
                .unionByName(item_rows.select("cause", F.col("product_id").alias("key"))))
    return {"daily_sales": daily.distinct(), "customer_lifetime_value": customers.distinct(),
            "product_performance": products.distinct()}


def cause_seeds(spark, landing, groups, manifest):
    frames = [spark.createDataFrame([], SEED_SCHEMA)]
    if "feed" in groups:
        frames.append(feed_seeds(spark, manifest))
    if "anomaly" in groups or "silver_anomaly" in groups:
        anomalies = read_json(f"{landing}/_anomaly_manifest.json")
        frames.append(anomaly_seeds(spark, landing, anomalies, silver_only="anomaly" not in groups))
    return reduce(DataFrame.unionByName, frames)


# --- comparison --------------------------------------------------------------------------

def _row_hash(columns):
    return F.sha2(F.concat_ws("|", *[F.coalesce(F.col(c).cast("string"), F.lit("<null>")) for c in columns]), 256)


def compare_mart(mart, legacy, modern, touched=None):
    """Compares one mart. touched is DataFrame(key, cause), or None for an exact comparison.
    Returns (summary dict, list of difference dicts)."""
    key, columns = MARTS[mart]
    values = [c for c in columns if c != key]
    numeric = [c for c in values if columns[c] in NUMERIC]

    def side(df, p):
        # One row per key. Duplicate keys are counted in "rows" and their measures summed, so
        # the totals still compare; the duplicate itself is reported as a difference.
        collapsed = df.groupBy(key).agg(
            F.count(F.lit(1)).alias("rows"),
            *[(F.sum(c) if c in numeric else F.min(c)).cast(columns[c]).alias(c) for c in values])
        return collapsed.select(F.col(key).alias(p + "key"), F.col("rows").alias(p + "rows"),
                                _row_hash(values).alias(p + "hash"), *[F.col(c).alias(p + c) for c in values])

    joined = side(legacy, "l_").join(side(modern, "m_"), F.col("l_key").eqNullSafe(F.col("m_key")), "full")
    kind = (F.when(F.col("m_rows").isNull(), "missing_in_modern")
            .when(F.col("l_rows").isNull(), "missing_in_legacy")
            .when(F.col("m_rows") > 1, "duplicate_in_modern")
            .when(F.col("l_rows") > 1, "duplicate_in_legacy")
            .when(F.col("l_hash") != F.col("m_hash"), "value_mismatch"))
    diffs = (joined.withColumn("kind", kind).filter(F.col("kind").isNotNull())
             .select(F.coalesce("l_key", "m_key").alias("key"), "kind",
                     F.concat_ws(",", *[F.when(~F.col("l_" + c).eqNullSafe(F.col("m_" + c)), F.lit(c))
                                        for c in values]).alias("columns"),
                     F.to_json(F.struct(*[F.col("l_" + c).alias(c) for c in values])).alias("legacy_values"),
                     F.to_json(F.struct(*[F.col("m_" + c).alias(c) for c in values])).alias("modern_values")))
    if touched is None:
        diffs = diffs.withColumn("causes", F.lit(None).cast("string"))
    else:
        causes = touched.groupBy(F.col("key").alias("t_key")).agg(
            F.concat_ws(",", F.sort_array(F.collect_set("cause"))).alias("causes"))
        diffs = diffs.join(causes, F.col("key").eqNullSafe(F.col("t_key")), "left").drop("t_key")

    rows = [r.asDict() for r in diffs.withColumn("key", F.col("key").cast("string")).orderBy("kind", "key").collect()]
    for r in rows:
        # A duplicate in gold breaks the mart's grain, whatever touched the key.
        r["explained"] = bool(r["causes"]) and r["kind"] != "duplicate_in_modern"
    duplicates = joined.agg(F.sum(F.when(F.col("l_rows") > 1, 1).otherwise(0)).alias("l"),
                            F.sum(F.when(F.col("m_rows") > 1, 1).otherwise(0)).alias("m")).first()
    totals_l = legacy.agg(F.count(F.lit(1)).alias("_rows"), *[F.sum(c).alias(c) for c in numeric]).first()
    totals_m = modern.agg(F.count(F.lit(1)).alias("_rows"), *[F.sum(c).alias(c) for c in numeric]).first()
    kinds = Counter(r["kind"] for r in rows)
    unexplained = sum(not r["explained"] for r in rows)
    summary = {
        "mart": mart,
        "legacy_rows": totals_l["_rows"], "modern_rows": totals_m["_rows"],
        "legacy_duplicate_keys": duplicates["l"] or 0, "modern_duplicate_keys": duplicates["m"] or 0,
        "missing_in_modern": kinds["missing_in_modern"], "missing_in_legacy": kinds["missing_in_legacy"],
        "value_mismatches": kinds["value_mismatch"],
        "explained": len(rows) - unexplained, "unexplained": unexplained,
        "totals": {c: [str(totals_l[c]), str(totals_m[c])] for c in numeric},
        "status": "ok" if unexplained == 0 else "FAIL",
    }
    return summary, rows


# --- entry point -------------------------------------------------------------------------

def print_report(run_id, dataset, results):
    print(f"Reconciliation {run_id}: dataset {dataset}")
    for legacy_name, groups, summaries, diffs in results:
        print(f"\nlegacy {legacy_name} vs modern; allowed causes: {', '.join(groups) or 'none (exact)'}")
        for s in summaries:
            print(f"  {s['mart']:<24} rows {s['legacy_rows']}/{s['modern_rows']}"
                  f"  duplicate keys {s['legacy_duplicate_keys']}/{s['modern_duplicate_keys']}"
                  f"  missing {s['missing_in_modern']}/{s['missing_in_legacy']}"
                  f"  mismatched {s['value_mismatches']}"
                  f"  explained {s['explained']}  unexplained {s['unexplained']}  {s['status']}")
            for column, (legacy_total, modern_total) in s["totals"].items():
                if legacy_total != modern_total:
                    print(f"      total {column}: legacy {legacy_total}, modern {modern_total}")
        unexplained = [d for d in diffs if not d["explained"]]
        for d in unexplained[:20]:
            print(f"  UNEXPLAINED {d['mart']} key={d['key']} {d['kind']} columns={d['columns']}")
            print(f"      legacy {d['legacy_values']}\n      modern {d['modern_values']}")
        if len(unexplained) > 20:
            print(f"  ... {len(unexplained) - 20} more unexplained differences")


def write_results(spark, schema, run_id, dataset, results):
    """Writes one summary row per mart and one row per difference to <schema>, replacing any
    rows already there for run_id."""
    run_at = datetime.now(timezone.utc).replace(tzinfo=None)
    summaries, differences = [], []
    for legacy_name, groups, marts, diffs in results:
        causes = ",".join(groups) or "none"
        summaries += [(run_id, run_at, dataset, legacy_name, causes, s["mart"], s["legacy_rows"], s["modern_rows"],
                       s["legacy_duplicate_keys"], s["modern_duplicate_keys"], s["missing_in_modern"],
                       s["missing_in_legacy"], s["value_mismatches"], s["explained"], s["unexplained"],
                       json.dumps(s["totals"]), s["status"]) for s in marts]
        differences += [(run_id, dataset, legacy_name, d["mart"], d["key"], d["kind"], d["columns"],
                         d["legacy_values"], d["modern_values"], d["causes"], d["explained"]) for d in diffs]
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    for table, rows, row_schema in (("reconciliation_summary", summaries, SUMMARY_SCHEMA),
                                    ("reconciliation_differences", differences, DIFF_SCHEMA)):
        name = f"{schema}.{table}"
        # A second attempt of the task keeps the job's run id (Phase 06 HANDOFF, Step 7: both failed
        # runs wrote twice), so replace that run's rows instead of adding a second set.
        if spark.catalog.tableExists(name):
            spark.sql(f"DELETE FROM {name} WHERE run_id = :run_id", args={"run_id": run_id})
        spark.createDataFrame(rows, row_schema).write.mode("append").saveAsTable(name)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Reconcile the gold marts with the legacy job's outputs.")
    parser.add_argument("--dataset", choices=sorted(PLANS), required=True,
                        help="which dataset the modern side was built from")
    parser.add_argument("--landing", required=True, help="dataset folder with batch_NNN folders and manifests")
    parser.add_argument("--legacy-root", required=True, help="folder with one legacy output folder per dataset")
    modern = parser.add_mutually_exclusive_group(required=True)
    modern.add_argument("--modern-schema", help="schema with the gold marts, for example workspace.retail_gold")
    modern.add_argument("--modern-csv", help="marts in the legacy CSV layout, for a local rehearsal")
    parser.add_argument("--results-schema", help="schema to append results to; omit to print only")
    parser.add_argument("--run-id", default=datetime.now(timezone.utc).strftime("local-%Y%m%dT%H%M%SZ"))
    args = parser.parse_args(argv)

    spark = SparkSession.builder.getOrCreate()
    if args.modern_schema:
        modern_marts = {m: read_table_mart(spark, args.modern_schema, m) for m in MARTS}
    else:
        modern_marts = {m: read_csv_mart(spark, args.modern_csv, m) for m in MARTS}
    manifest = read_json(f"{args.landing}/_manifest.json")

    results = []
    for legacy_name, groups in PLANS[args.dataset]:
        touched = (touched_keys(spark, args.landing, cause_seeds(spark, args.landing, groups, manifest))
                   if groups else {})
        summaries, diffs = [], []
        for mart in MARTS:
            legacy = read_csv_mart(spark, f"{args.legacy_root}/{legacy_name}", mart)
            summary, rows = compare_mart(mart, legacy, modern_marts[mart], touched.get(mart))
            summaries.append(summary)
            diffs += [dict(r, mart=mart) for r in rows]
        results.append((legacy_name, groups, summaries, diffs))

    print_report(args.run_id, args.dataset, results)
    if args.results_schema:
        write_results(spark, args.results_schema, args.run_id, args.dataset, results)
        print(f"\nResults written to {args.results_schema}.reconciliation_summary and reconciliation_differences")
    failed = any(s["status"] != "ok" for _, _, summaries, _ in results for s in summaries)
    print(f"\nRESULT: {'FAIL' if failed else 'PASS'}")
    return 1 if failed else 0


if __name__ == "__main__":
    # No sys.exit(): the job runner reports any SystemExit, even code 0, as a failed task (first
    # job run, Phase 06 HANDOFF). An exception is the failure signal, locally and in the job.
    if main() != 0:
        raise RuntimeError("reconciliation found unexplained differences; see the report above")
