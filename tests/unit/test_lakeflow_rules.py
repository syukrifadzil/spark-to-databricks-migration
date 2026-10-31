"""The pipeline's contract rules, evaluated by local Spark, must reject exactly what the Phase 01
validator rejects, rule for rule, on every row of the committed samples. The Spark tests are
skipped without pyspark or Java."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from data.generators import common, validate
from lakeflow import retail_rules as rr

SAMPLES = Path(__file__).resolve().parents[2] / "data" / "samples"


def _java_runs():
    home = os.environ.get("JAVA_HOME")
    java = os.path.join(home, "bin", "java") if home else shutil.which("java")
    return bool(java) and subprocess.run([java, "-version"], capture_output=True).returncode == 0


@pytest.fixture(scope="module")
def spark():
    pytest.importorskip("pyspark")
    if not _java_runs():
        pytest.skip("no working Java runtime")
    from pyspark.sql import SparkSession
    session = (SparkSession.builder.master("local[1]").appName("lakeflow_rules")
               .config("spark.ui.enabled", "false").getOrCreate())
    yield session
    session.stop()


def test_rule_names_follow_the_validator():
    contract = common.load_contract()
    rules = rr.entity_rules(contract, "payments")
    assert {"payments.amount.required", "payments.amount.type", "payments.amount.range",
            "payments.method.domain", "payments.event_id.domain"} <= set(rules)
    assert all(pred.startswith("coalesce(") for pred in rules.values())


@pytest.mark.parametrize("dataset", ["clean", "anomalous"])
def test_failed_rules_match_the_validator(spark, dataset):
    contract = common.load_contract()
    for entity in common.ENTITIES:
        spec = contract["entities"][entity]["columns"] + contract["feed_columns"]
        names = [c["name"] for c in spec]
        rows, expected = [], []
        for path in sorted((SAMPLES / dataset).glob(f"batch_*/{entity}.csv")):
            for row in common.read_csv(path)[1]:
                # Auto Loader reads an empty CSV field as null.
                rows.append(tuple(row.get(n) or None for n in names))
                expected.append(sorted(rule for _, rule in validate.row_problems(row, spec, entity)))
        df = spark.createDataFrame(rows, rr.bronze_schema(contract, entity))
        failed = df.selectExpr(f"{rr.failed_rules_sql(rr.entity_rules(contract, entity))} AS f").collect()
        assert [sorted(r.f) for r in failed] == expected, entity


def test_typed_columns_parse_valid_rows(spark):
    contract = common.load_contract()
    path = SAMPLES / "clean" / "batch_000" / "payments.csv"
    spec = contract["entities"]["payments"]["columns"] + contract["feed_columns"]
    rows = [tuple(r[c["name"]] for c in spec) + ("file", None) for r in common.read_csv(path)[1]]
    schema = rr.bronze_schema(contract, "payments") + ", _source_file STRING, _ingested_at TIMESTAMP"
    typed = spark.createDataFrame(rows, schema).selectExpr(*rr.typed_columns(contract, "payments"))
    assert dict(typed.dtypes)["amount"] == "decimal(18,2)"
    assert dict(typed.dtypes)["payment_at"] == "timestamp"
    assert typed.filter("amount IS NULL OR payment_at IS NULL OR source_updated_at IS NULL").count() == 0
