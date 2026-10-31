"""Nightly retail reporting job: the legacy baseline.

This is the job the migration replaces, written the way many long-lived batch jobs are:
one script, reload everything, stack files, overwrite outputs, print logging. Its known
limitations are marked LIMITATION n and explained in
phases/phase_02_legacy_spark/EXPLANATION.md. They are deliberate: they are the behaviour
the Lakehouse is reconciled against, so do not fix them here.

Business rules for the three outputs are defined in docs/data_contracts.md section 7.

Run from the repository root (needs Java and pyspark):

    python -m legacy_spark.retail_nightly_job --input data/raw/clean --output output/legacy/clean
"""
import argparse
import glob
import json
import os
import sys
import time
from datetime import datetime, timezone
from functools import reduce

from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F

# LIMITATION 1: column lists are hard-coded here rather than read from the data contract.
COLUMNS = {
    "customers": ["customer_id", "name", "email", "region", "created_at", "updated_at"],
    "products": ["product_id", "product_name", "category", "price", "status"],
    "orders": ["order_id", "customer_id", "order_date", "status"],
    "order_items": ["order_item_id", "order_id", "product_id", "quantity", "unit_price"],
    "payments": ["payment_id", "order_id", "payment_type", "amount", "method", "status", "payment_at"],
}
KEYS = {"customers": "customer_id", "products": "product_id", "orders": "order_id"}
SOLD_STATUSES = ["paid", "shipped", "delivered"]
TS_FORMAT = "yyyy-MM-dd'T'HH:mm:ssX"
METRICS_SQL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sql", "baseline_metrics.sql")


def log(message):
    # LIMITATION 9: print logging. No levels, no run id, nothing a monitor can parse.
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}", flush=True)


def read_all(spark, input_dir, entity):
    """Read one entity from every batch folder and stack the files in folder order."""
    # LIMITATION 2: full reload. Every run rereads every batch ever delivered.
    frames = []
    for file_no, folder in enumerate(sorted(glob.glob(os.path.join(input_dir, "batch_*")))):
        path = os.path.join(folder, entity + ".csv")
        if not os.path.exists(path):
            continue
        df = spark.read.option("header", True).csv(path)
        # LIMITATION 6: extra columns are silently dropped here; a missing column crashes the job.
        df = df.select(*COLUMNS[entity])
        frames.append(df.withColumn("_file_no", F.lit(file_no)).withColumn("_row_no", F.monotonically_increasing_id()))
    df = reduce(DataFrame.union, frames)
    # LIMITATION 9: an extra full scan, only to print a count.
    log(f"read {entity}: {df.count()} rows from {len(frames)} files")
    return df


def last_file_wins(df, key):
    """Keep one row per key: the one read last."""
    # LIMITATION 3: arrival order decides, not source_updated_at. A late or replayed older
    # version overwrites a newer one.
    window = Window.partitionBy(key).orderBy(F.col("_file_no").desc(), F.col("_row_no").desc())
    return (df.withColumn("_rn", F.row_number().over(window))
            .filter(F.col("_rn") == 1)
            .drop("_rn", "_file_no", "_row_no"))


def build_marts(spark, input_dir):
    customers = last_file_wins(read_all(spark, input_dir, "customers"), "customer_id")
    products = last_file_wins(read_all(spark, input_dir, "products"), "product_id")
    orders = last_file_wins(read_all(spark, input_dir, "orders"), "order_id")
    # LIMITATION 4: items and payments are assumed insert-only and stacked without
    # deduplication, so a replayed row is counted twice.
    items = read_all(spark, input_dir, "order_items").drop("_file_no", "_row_no")
    payments = read_all(spark, input_dir, "payments").drop("_file_no", "_row_no")

    # LIMITATION 5: plain casts with ANSI mode off. Malformed values become null and drop
    # out of totals silently; negative amounts and null keys are accepted.
    # LIMITATION 8: money is a double, rounded only when written.
    orders = orders.withColumn("business_date", F.to_date(F.to_timestamp("order_date", TS_FORMAT)))
    items = (items.withColumn("quantity", F.col("quantity").cast("int"))
             .withColumn("unit_price", F.col("unit_price").cast("double"))
             .withColumn("line_total", F.col("quantity") * F.col("unit_price")))
    payments = (payments.filter(F.col("status") == "succeeded")
                .withColumn("amount", F.col("amount").cast("double"))
                .withColumn("signed_amount", F.when(F.col("payment_type") == "charge", F.col("amount"))
                            .when(F.col("payment_type") == "refund", -F.col("amount")))
                .withColumn("business_date", F.to_date(F.to_timestamp("payment_at", TS_FORMAT))))

    sold = orders.filter(F.col("status").isin(SOLD_STATUSES))
    # LIMITATION 7: inner joins. Lines whose order is missing vanish without a trace, and
    # lines for unknown products never reach product_performance.
    sold_lines = items.join(sold.select("order_id", "customer_id", "business_date"), "order_id")

    # daily_sales
    per_date = [
        orders.groupBy("business_date").agg(F.count("*").alias("orders_placed")),
        sold.groupBy("business_date").agg(F.count("*").alias("orders_sold")),
        sold_lines.groupBy("business_date").agg(F.sum("quantity").alias("items_sold"),
                                                F.sum("line_total").alias("gross_sales")),
        payments.groupBy("business_date").agg(
            F.sum(F.when(F.col("payment_type") == "charge", F.col("amount")).otherwise(0)).alias("charges"),
            F.sum(F.when(F.col("payment_type") == "refund", F.col("amount")).otherwise(0)).alias("refunds")),
    ]
    daily = reduce(lambda a, b: a.join(b, "business_date", "full"), per_date).na.fill(0)
    daily = (daily.withColumn("net_payments", F.col("charges") - F.col("refunds"))
             .select("business_date", "orders_placed", "orders_sold", "items_sold",
                     *[F.round(c, 2).alias(c) for c in ("gross_sales", "charges", "refunds", "net_payments")])
             .orderBy("business_date"))

    # customer_lifetime_value
    customer_orders = sold.groupBy("customer_id").agg(F.min("business_date").alias("first_order_date"),
                                                      F.max("business_date").alias("last_order_date"),
                                                      F.count("*").alias("orders_sold"))
    customer_sales = sold_lines.groupBy("customer_id").agg(F.sum("line_total").alias("lifetime_gross_sales"))
    customer_net = (payments.groupBy("order_id").agg(F.sum("signed_amount").alias("net"))
                    .join(orders.select("order_id", "customer_id"), "order_id")
                    .groupBy("customer_id").agg(F.sum("net").alias("lifetime_net_paid")))
    clv = (customers.select("customer_id", "region")
           .join(customer_orders, "customer_id", "left")
           .join(customer_sales, "customer_id", "left")
           .join(customer_net, "customer_id", "left")
           .na.fill(0, ["orders_sold", "lifetime_gross_sales", "lifetime_net_paid"])
           .select("customer_id", "region", "first_order_date", "last_order_date", "orders_sold",
                   F.round("lifetime_gross_sales", 2).alias("lifetime_gross_sales"),
                   F.round("lifetime_net_paid", 2).alias("lifetime_net_paid"))
           .orderBy("customer_id"))

    # product_performance
    product_sales = sold_lines.groupBy("product_id").agg(F.sum("quantity").alias("units_sold"),
                                                        F.sum("line_total").alias("gross_sales"),
                                                        F.countDistinct("order_id").alias("orders_sold"))
    performance = (products.select("product_id", "product_name", "category", "status")
                   .join(product_sales, "product_id", "left")
                   .na.fill(0, ["units_sold", "gross_sales", "orders_sold"])
                   .select("product_id", "product_name", "category", "status", "units_sold",
                           F.round("gross_sales", 2).alias("gross_sales"), "orders_sold")
                   .orderBy("product_id"))

    return {"daily_sales": daily, "customer_lifetime_value": clv, "product_performance": performance}


def write_mart(df, output_dir, name):
    # LIMITATION 10: overwrite in place. A failure part-way leaves some outputs new and some
    # old, and there is no previous version to roll back to.
    df.coalesce(1).write.mode("overwrite").option("header", True).csv(os.path.join(output_dir, name))


def baseline_metrics(spark, marts):
    """Run sql/baseline_metrics.sql over the marts. Returns {metric: value as string}."""
    for name, df in marts.items():
        df.createOrReplaceTempView(name)
    with open(METRICS_SQL, encoding="utf-8") as f:
        sql = "\n".join(line for line in f.read().splitlines() if not line.lstrip().startswith("--"))
    return {row["metric"]: str(row["value"]) for row in spark.sql(sql).collect()}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Legacy nightly retail reporting job.")
    parser.add_argument("--input", default="data/raw/clean", help="dataset folder containing batch_NNN folders")
    parser.add_argument("--output", default="output/legacy/clean", help="folder for the three outputs")
    args = parser.parse_args(argv)

    started = time.time()
    log(f"start input={args.input} output={args.output}")
    spark = (SparkSession.builder.master("local[*]").appName("retail_nightly_legacy")
             # Pinned so the baseline is the same on every machine (see docs/adr/0006).
             .config("spark.sql.session.timeZone", "Asia/Kuala_Lumpur")
             # The job predates Spark 4's ANSI default; it relies on lenient casts (LIMITATION 5).
             .config("spark.sql.ansi.enabled", "false")
             .config("spark.sql.legacy.timeParserPolicy", "CORRECTED")
             .config("spark.sql.shuffle.partitions", "4")
             .config("spark.ui.enabled", "false")
             .getOrCreate())
    spark.sparkContext.setLogLevel("WARN")

    # Materialise each output once, so the files and the metrics come from the same rows. Without
    # this the metrics query recomputes the whole plan, and on the anomalous dataset it returned
    # different daily order counts from the written files (Phase 02 handoff, O1).
    marts = {name: df.localCheckpoint() for name, df in build_marts(spark, args.input).items()}
    for name, df in marts.items():
        write_mart(df, args.output, name)
        log(f"wrote {name}")
    metrics = baseline_metrics(spark, marts)
    report = {
        "input": args.input,
        "spark_version": spark.version,
        "started_at_utc": datetime.fromtimestamp(started, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "duration_seconds": round(time.time() - started, 1),
        "metrics": metrics,
    }
    with open(os.path.join(args.output, "baseline_metrics.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)
    log(f"done in {report['duration_seconds']} s; metrics in {args.output}/baseline_metrics.json")
    spark.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
