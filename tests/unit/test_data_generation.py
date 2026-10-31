"""Tests for the synthetic data generator, anomaly injector and validator, using the tiny preset."""
import re
from collections import defaultdict
from decimal import Decimal

import pytest

from data.generators import common, generate, inject_anomalies, validate


def tiny(**overrides):
    return generate.Config(**{**generate.PRESETS["tiny"], **overrides}, preset="tiny")


def tree_digest(root):
    return {p.relative_to(root).as_posix(): common.sha256_file(p) for p in sorted(root.rglob("*")) if p.is_file()}


def rows_by_event(path):
    return {r["event_id"]: r for r in common.read_csv(path)[1]}


@pytest.fixture(scope="module")
def clean(tmp_path_factory):
    out = tmp_path_factory.mktemp("datasets") / "clean"
    generate.run(tiny(), out)
    return out


# --- configuration errors ----------------------------------------------------------

@pytest.mark.parametrize("overrides", [
    dict(customers=0), dict(products=3), dict(batch_orders=-1), dict(batches=0),
    dict(late_rate=1.5), dict(history_days=0),
])
def test_invalid_configuration_is_rejected(overrides):
    with pytest.raises(ValueError):
        generate.generate(tiny(**overrides), common.load_contract())


def test_output_directory_is_protected(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "notes.txt").write_text("keep me")
    assert generate.main(["--preset", "tiny", "--out", str(out)]) == 2
    assert generate.main(["--preset", "tiny", "--out", str(out), "--force"]) == 2  # no _manifest.json: not ours
    assert (out / "notes.txt").exists()


def test_unknown_scenario_is_rejected(clean, tmp_path):
    with pytest.raises(ValueError):
        inject_anomalies.inject(clean, tmp_path / "x", ["no_such_scenario"])


# --- reproducibility ------------------------------------------------------------------

def test_same_configuration_gives_identical_files(clean, tmp_path):
    generate.run(tiny(), tmp_path / "again")
    assert tree_digest(tmp_path / "again") == tree_digest(clean)


def test_different_seed_changes_the_data(clean, tmp_path):
    generate.run(tiny(seed=43), tmp_path / "other")
    assert tree_digest(tmp_path / "other") != tree_digest(clean)


# --- row counts --------------------------------------------------------------------------

def test_exact_counts(clean):
    cfg, manifest = tiny(), common.read_json(clean / "_manifest.json")
    snapshot = manifest["batches"]["batch_000"]["files"]
    assert snapshot["customers.csv"]["rows"] == cfg.customers
    assert snapshot["products.csv"]["rows"] == cfg.products
    assert snapshot["orders.csv"]["rows"] == cfg.orders
    assert manifest["expected_rows"]["customers"] == cfg.customers + cfg.batches * cfg.batch_customers
    assert manifest["expected_rows"]["orders"] == cfg.orders + cfg.batches * cfg.batch_orders
    assert manifest["expected_rows"]["products"] == cfg.products
    assert sorted(manifest["batches"]) == [common.batch_name(i) for i in range(cfg.batches + 1)]


# --- contracts, keys, money and ground truth --------------------------------------------

def test_clean_dataset_passes_validation(clean):
    report = validate.validate(clean)
    assert report.ok, report.summary()


def test_money_rounds_half_up():
    assert common.money("0.125") == Decimal("0.13")   # half-even would give 0.12
    assert common.money("2.675") == Decimal("2.68")
    assert common.fmt_money(Decimal("4")) == "4.00"


def test_paid_orders_match_their_charges(clean):
    """Recomputed independently of the validator from the expected final state."""
    state = {e: common.read_csv(clean / "_expected" / f"{e}.csv")[1] for e in ("orders", "order_items", "payments")}
    totals, charges = defaultdict(Decimal), defaultdict(Decimal)
    for item in state["order_items"]:
        totals[item["order_id"]] += int(item["quantity"]) * Decimal(item["unit_price"])
    for p in state["payments"]:
        assert re.fullmatch(r"\d+\.\d{2}", p["amount"])
        if p["status"] == "succeeded" and p["payment_type"] == "charge":
            charges[p["order_id"]] += Decimal(p["amount"])
    paid = [o["order_id"] for o in state["orders"] if o["status"] in ("paid", "shipped", "delivered")]
    assert paid
    assert all(charges[oid] == totals[oid] for oid in paid)


# --- incremental semantics -------------------------------------------------------------

def test_clean_dataset_exercises_every_change_type(clean):
    manifest = common.read_json(clean / "_manifest.json")
    assert manifest["late_arrivals"] and manifest["replays"] and manifest["corrections"]
    change_types = set()
    for batch in manifest["batches"]:
        for entity in common.ENTITIES:
            change_types |= {r["change_type"] for r in common.read_csv(clean / batch / f"{entity}.csv")[1]}
    assert change_types == {"snapshot", "insert", "update", "correction"}


def test_snapshot_has_one_row_per_key(clean):
    contract = common.load_contract()
    for entity in common.ENTITIES:
        rows = common.read_csv(clean / "batch_000" / f"{entity}.csv")[1]
        keys = [r[common.primary_key(contract, entity)] for r in rows]
        assert len(keys) == len(set(keys))
        assert {r["change_type"] for r in rows} <= {"snapshot"}


def test_late_arrivals_and_replays_are_delivered_as_declared(clean):
    manifest = common.read_json(clean / "_manifest.json")
    for late in manifest["late_arrivals"]:
        assert late["delivered_in"] > late["window_batch"]
        assert late["event_id"] in rows_by_event(clean / late["delivered_in"] / f"{late['entity']}.csv")
        assert late["event_id"] not in rows_by_event(clean / late["window_batch"] / f"{late['entity']}.csv")
    for rep in manifest["replays"]:
        original = rows_by_event(clean / rep["original_batch"] / f"{rep['entity']}.csv")[rep["event_id"]]
        assert rows_by_event(clean / rep["replayed_in"] / f"{rep['entity']}.csv")[rep["event_id"]] == original


# --- anomaly injection and duplicate detection -----------------------------------------

@pytest.mark.parametrize("scenario", inject_anomalies.SCENARIOS)
def test_each_scenario_is_detected_exactly(clean, tmp_path, scenario):
    result = inject_anomalies.inject(clean, tmp_path / scenario, [scenario], count=3)
    assert len(result["batches"]) == 1
    assert all(entry["count"] > 0 for entry in result["entries"])
    report = validate.validate(tmp_path / scenario)
    assert report.ok, report.summary()


def test_scenario_output_does_not_depend_on_other_scenarios(clean, tmp_path):
    alone = inject_anomalies.inject(clean, tmp_path / "alone", ["null_required"], count=3)
    together = inject_anomalies.inject(clean, tmp_path / "all", inject_anomalies.SCENARIOS, count=3)
    batch = next(iter(alone["batches"]))
    assert alone["batches"][batch] == together["batches"][batch]
    report = validate.validate(tmp_path / "all")
    assert report.ok, report.summary()


def test_clean_source_is_not_modified(clean, tmp_path):
    before = tree_digest(clean)
    inject_anomalies.inject(clean, tmp_path / "anomalous", inject_anomalies.SCENARIOS, count=3)
    assert tree_digest(clean) == before


def test_validator_reports_undeclared_anomalies(clean, tmp_path):
    out = tmp_path / "undeclared"
    inject_anomalies.inject(clean, out, ["null_required"], count=3)
    manifest_path = out / "_anomaly_manifest.json"
    manifest = common.read_json(manifest_path)
    manifest["entries"] = []
    common.write_json(manifest_path, manifest)
    report = validate.validate(out)
    assert not report.ok
    assert "required" in report.mismatches()
