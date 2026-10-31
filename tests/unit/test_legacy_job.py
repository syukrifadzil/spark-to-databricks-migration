"""Runs the legacy job on the committed tiny samples and checks it against a plain-Python
statement of its documented semantics. Skipped when pyspark or a Java runtime is missing."""
import csv
import json
import os
import shutil
import subprocess
from decimal import Decimal
from pathlib import Path

import pytest

pytest.importorskip("pyspark")


def _java_runs():
    home = os.environ.get("JAVA_HOME")
    java = os.path.join(home, "bin", "java") if home else shutil.which("java")
    # macOS ships a /usr/bin/java stub that exists but fails without a JDK, so run it.
    return bool(java) and subprocess.run([java, "-version"], capture_output=True).returncode == 0


if not _java_runs():
    pytest.skip("no working Java runtime", allow_module_level=True)

from data.generators import common  # noqa: E402
from legacy_spark import retail_nightly_job as job  # noqa: E402

SAMPLES = Path(__file__).resolve().parents[2] / "data" / "samples"


def read_mart(out, name):
    [part] = list((out / name).glob("part-*.csv"))
    with open(part, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def total(rows, column):
    return sum((Decimal(r[column]) for r in rows), Decimal(0))


def legacy_reference(root):
    """Last file wins for customers, products and orders; items and payments stacked as read."""
    current = {entity: {} for entity in job.KEYS}
    stacked = {"order_items": [], "payments": []}
    for batch in sorted(root.glob("batch_*")):
        for entity in common.ENTITIES:
            path = batch / f"{entity}.csv"
            if not path.exists():
                continue
            rows = common.read_csv(path)[1]
            if entity in stacked:
                stacked[entity] += rows
            else:
                current[entity].update({r[job.KEYS[entity]]: r for r in rows})
    sold = {oid for oid, o in current["orders"].items() if o["status"] in job.SOLD_STATUSES}
    succeeded = [p for p in stacked["payments"] if p["status"] == "succeeded"]
    return {
        "customers": len(current["customers"]),
        "products": len(current["products"]),
        "orders_sold": len(sold),
        "gross_sales": sum((int(i["quantity"]) * Decimal(i["unit_price"])
                            for i in stacked["order_items"] if i["order_id"] in sold), Decimal(0)),
        "charges": sum((Decimal(p["amount"]) for p in succeeded if p["payment_type"] == "charge"), Decimal(0)),
        "refunds": sum((Decimal(p["amount"]) for p in succeeded if p["payment_type"] == "refund"), Decimal(0)),
    }


@pytest.fixture(scope="module")
def clean_run(tmp_path_factory):
    out = tmp_path_factory.mktemp("legacy") / "clean"
    assert job.main(["--input", str(SAMPLES / "clean"), "--output", str(out)]) == 0
    return out


def test_marts_have_the_documented_grain(clean_run):
    expected = legacy_reference(SAMPLES / "clean")
    assert len(read_mart(clean_run, "customer_lifetime_value")) == expected["customers"]
    assert len(read_mart(clean_run, "product_performance")) == expected["products"]
    daily = read_mart(clean_run, "daily_sales")
    assert daily and all(r["business_date"] for r in daily)
    assert len({r["business_date"] for r in daily}) == len(daily)


def test_totals_follow_the_legacy_semantics(clean_run):
    expected = legacy_reference(SAMPLES / "clean")
    daily = read_mart(clean_run, "daily_sales")
    assert total(daily, "orders_sold") == expected["orders_sold"]
    assert total(daily, "gross_sales") == expected["gross_sales"]
    assert total(daily, "charges") == expected["charges"]
    assert total(daily, "refunds") == expected["refunds"]
    assert total(daily, "net_payments") == expected["charges"] - expected["refunds"]


def test_baseline_metrics_agree_with_the_outputs(clean_run):
    metrics = json.loads((clean_run / "baseline_metrics.json").read_text())["metrics"]
    gross = Decimal(metrics["daily_sales.gross_sales"])
    assert gross == total(read_mart(clean_run, "daily_sales"), "gross_sales")
    # Clean samples have no orphans or bad dates, so all three marts agree on gross sales.
    assert Decimal(metrics["customer_lifetime_value.lifetime_gross_sales"]) == gross
    assert Decimal(metrics["product_performance.gross_sales"]) == gross
    assert Decimal(metrics["daily_sales.null_business_date_rows"]) == 0


def test_job_completes_on_anomalous_input(tmp_path):
    out = tmp_path / "anomalous"
    assert job.main(["--input", str(SAMPLES / "anomalous"), "--output", str(out)]) == 0
    for name in ("daily_sales", "customer_lifetime_value", "product_performance"):
        assert read_mart(out, name)
    # The metrics must describe the written files, including their null-date rows (O1).
    metrics = json.loads((out / "baseline_metrics.json").read_text())["metrics"]
    daily = read_mart(out, "daily_sales")
    for column in ("orders_placed", "orders_sold", "gross_sales", "charges"):
        assert Decimal(metrics[f"daily_sales.{column}"]) == total(daily, column)
    assert total(daily, "orders_sold") == total(read_mart(out, "customer_lifetime_value"), "orders_sold")
