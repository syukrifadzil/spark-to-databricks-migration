"""The reconciliation engine on local Spark: the legacy job's own outputs on the committed samples,
plus a small hand-made landing folder for the cause-to-key rules. Skipped without pyspark or Java."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

pytest.importorskip("pyspark")

SAMPLES = Path(__file__).resolve().parents[2] / "data" / "samples"
MARTS = ("daily_sales", "customer_lifetime_value", "product_performance")


def _java_runs():
    home = os.environ.get("JAVA_HOME")
    java = os.path.join(home, "bin", "java") if home else shutil.which("java")
    return bool(java) and subprocess.run([java, "-version"], capture_output=True).returncode == 0


if not _java_runs():
    pytest.skip("no working Java runtime", allow_module_level=True)

from legacy_spark import retail_nightly_job as job  # noqa: E402
from reconciliation import reconcile as rc  # noqa: E402


@pytest.fixture(scope="module")
def legacy(tmp_path_factory):
    # The legacy job starts and stops its own session, so run it before ours exists.
    out = tmp_path_factory.mktemp("legacy")
    for dataset in ("clean", "anomalous"):
        assert job.main(["--input", str(SAMPLES / dataset), "--output", str(out / dataset)]) == 0
    return out


@pytest.fixture(scope="module")
def spark(legacy):
    from pyspark.sql import SparkSession
    session = (SparkSession.builder.master("local[1]").appName("reconcile")
               .config("spark.ui.enabled", "false").config("spark.sql.shuffle.partitions", "1").getOrCreate())
    yield session
    session.stop()


def marts(spark, folder):
    return {m: rc.read_csv_mart(spark, str(folder), m) for m in MARTS}


def test_identical_outputs_reconcile_exactly(spark, legacy):
    clean = marts(spark, legacy / "clean")
    for mart in MARTS:
        summary, rows = rc.compare_mart(mart, clean[mart], clean[mart])
        assert rows == [] and summary["status"] == "ok", mart
        assert summary["legacy_rows"] == summary["modern_rows"] > 0


def test_every_difference_without_a_cause_is_unexplained(spark, legacy):
    from pyspark.sql import functions as F
    daily = marts(spark, legacy / "clean")["daily_sales"]
    dates = [r.business_date for r in daily.orderBy("business_date").limit(3).collect()]
    changed = (daily.filter(F.col("business_date") != dates[0])          # one key missing
               .withColumn("charges", F.when(F.col("business_date") == dates[1], F.col("charges") + 1)
                           .otherwise(F.col("charges")))                 # one value changed
               .unionByName(daily.filter(F.col("business_date") == dates[2])))  # one key duplicated
    summary, rows = rc.compare_mart("daily_sales", daily, changed)
    found = {(r["key"], r["kind"]) for r in rows}
    assert found == {(str(dates[0]), "missing_in_modern"), (str(dates[1]), "value_mismatch"),
                     (str(dates[2]), "duplicate_in_modern")}
    assert next(r for r in rows if r["kind"] == "value_mismatch")["columns"] == "charges"
    assert summary["unexplained"] == 3 and summary["status"] == "FAIL"
    assert summary["modern_duplicate_keys"] == 1


def test_anomaly_batches_explain_every_legacy_difference(spark, legacy):
    # The anomalous sample is the clean sample plus one batch per scenario, so every difference
    # between the two legacy outputs must trace to a row in a scenario batch.
    landing = str(SAMPLES / "anomalous")
    manifest = json.loads((SAMPLES / "anomalous" / "_anomaly_manifest.json").read_text())
    touched = rc.touched_keys(spark, landing, rc.anomaly_seeds(spark, landing, manifest))
    clean, anomalous = marts(spark, legacy / "clean"), marts(spark, legacy / "anomalous")
    explained = 0
    for mart in MARTS:
        summary, rows = rc.compare_mart(mart, anomalous[mart], clean[mart], touched[mart])
        assert summary["unexplained"] == 0, [r for r in rows if not r["explained"]]
        explained += summary["explained"]
    # The null customer_id rows collapse into one legacy row with a null key (Phase 02, L5).
    assert explained > 0


def test_main_reads_the_manifests_and_passes_on_identical_outputs(spark, legacy, tmp_path):
    # End to end through main(), which reads _manifest.json. Spark skips files named "_*", so a
    # manifest read through spark.read finds nothing; the first rehearsal failed that way.
    root = tmp_path / "legacy"
    for name in ("ordered", "clean"):
        shutil.copytree(legacy / "clean", root / name)
    assert rc.main(["--dataset", "clean", "--landing", str(SAMPLES / "clean"),
                    "--legacy-root", str(root), "--modern-csv", str(legacy / "clean")]) == 0


def write_csv(path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join([",".join(header)] + [",".join(r) for r in rows]) + "\n")


def test_causes_touch_dates_customers_and_products(spark, tmp_path):
    write_csv(tmp_path / "batch_000" / "orders.csv", ["order_id", "customer_id", "order_date", "status"], [
        ("O1", "C1", "2025-12-31T16:30:00Z", "paid"),     # 00:30 on 1 January in Kuala Lumpur
        ("O1", "C1", "not-a-timestamp", "paid"),
        ("O2", "C2", "2025-12-01T00:00:00Z", "paid")])
    write_csv(tmp_path / "batch_000" / "order_items.csv", ["order_item_id", "order_id", "product_id"], [
        ("I1", "O1", "P1"), ("I2", "O1", "P2"), ("I3", "O2", "P3")])
    write_csv(tmp_path / "batch_000" / "payments.csv", ["payment_id", "order_id", "payment_at"], [
        ("Y1", "O2", "2025-12-05T03:00:00Z"), ("Y1", "", "2025-12-05T03:00:00Z")])
    seeds = spark.createDataFrame([("order", "orders", "O1"), ("item", "order_items", "I3"),
                                   ("payment", "payments", "Y1"), ("customer", "customers", None)], rc.SEED_SCHEMA)
    touched = rc.touched_keys(spark, str(tmp_path), seeds)

    def keys(mart, cause):
        return {None if r.key is None else str(r.key)
                for r in touched[mart].filter(f"cause = '{cause}'").collect()}

    assert keys("daily_sales", "order") == {"2026-01-01", None}
    assert keys("customer_lifetime_value", "order") == {"C1"}
    assert keys("product_performance", "order") == {"P1", "P2"}
    assert keys("daily_sales", "item") == {"2025-12-01"}
    assert keys("product_performance", "item") == {"P3"}
    assert keys("daily_sales", "payment") == {"2025-12-05"}
    assert keys("customer_lifetime_value", "payment") == {"C2"}
    assert keys("product_performance", "payment") == set()
    assert keys("customer_lifetime_value", "customer") == {None}
