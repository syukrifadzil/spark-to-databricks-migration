"""Copy a clean dataset and add anomaly scenarios, each in its own batch folder.

Run from the repository root:

    python -m data.generators.inject_anomalies --source data/raw/clean --out data/raw/anomalous --all

The clean dataset is never modified. Every scenario writes new rows into its own batch,
batch_(N + position of the scenario in SCENARIOS), with its own random stream, so a
scenario's output is identical whether it runs alone or with others. Injected rows use
event ids EVT-Annn-nnnnn and new keys with an X marker (ORD-X..., PAY-X...), which cannot
collide with clean data. _anomaly_manifest.json lists every affected identifier, the check
that must detect it and the expected downstream behaviour.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from data.generators.common import (
    DAY, ENTITIES, Rng, allowed, batch_name, fmt_ts, header, load_contract, midnight_utc, parse_ts,
    prepare_out_dir, read_csv, read_json, sha256_file, write_csv, write_json,
)

SCENARIOS = ("duplicate_key_conflict", "null_required", "invalid_reference", "negative_amount", "payment_mismatch",
             "malformed_timestamp", "malformed_type", "schema_evolution", "late_arrival", "replay")
BAD_TIMESTAMPS = ("31/12/2025 10:00:00", "2026-13-01T00:00:00Z", "not-a-timestamp")
BAD_INTEGERS = ("two", "1.5", "3 units")
BAD_DECIMALS = ("12,50", "abc", "1.234")


class Batch:
    """The batch one scenario writes into."""

    def __init__(self, index: int, as_of, scenario: str):
        self.index, self.name, self.scenario = index, batch_name(index), scenario
        self.start = as_of + (index - 1) * DAY
        self.files = defaultdict(list)
        self.headers = {}
        self.entries = []
        self._n = 0

    def _tick(self) -> int:
        self._n += 1
        return self._n

    def ts(self) -> str:
        """A timestamp inside this batch's window, later than every clean record."""
        return fmt_ts(self.start + timedelta(seconds=self._tick()))

    def new_key(self, prefix: str) -> str:
        return f"{prefix}-X{self.index:03d}{self._tick():05d}"

    def emit(self, entity: str, row: dict, change_type: str, ts: str | None = None) -> str:
        eid = f"EVT-A{self.index:03d}-{self._tick():05d}"
        self.files[entity].append(dict(row, source_updated_at=ts or self.ts(), change_type=change_type,
                                       batch_id=self.name, event_id=eid))
        return eid

    def record(self, entity: str, check: str, ids: list[str], expected_behaviour: str, silver_effect: str) -> None:
        self.entries.append({"scenario": self.scenario, "batch": self.name, "entity": entity, "check": check,
                             "ids": sorted(ids), "count": len(ids), "expected_behaviour": expected_behaviour,
                             "silver_effect": silver_effect})


# --- scenarios -------------------------------------------------------------------
# Each takes (batch, rng, source, k). source.state holds the clean final state from _expected/.

def duplicate_key_conflict(b, rng, src, k):
    methods = allowed(src.contract, "payments", "method")
    ids = []
    for p in rng.sample(src.state["payments"], k):
        row = dict(p, method=rng.choice([m for m in methods if m != p["method"]]))
        ids.append(b.emit("payments", row, "update", ts=p["source_updated_at"]))
    b.record("payments", "sequence_conflict", ids,
             "Same payment_id and source_updated_at as an existing row, different method. Bronze keeps both; "
             "silver keeps the row with the higher event_id (this one); flagged as a sequence conflict.",
             "method changes for the affected payments")


def null_required(b, rng, src, k):
    for entity, column in (("customers", "customer_id"), ("orders", "status"), ("payments", "order_id")):
        ids = [b.emit(entity, dict(r, **{column: ""}), "update") for r in rng.sample(src.state[entity], k)]
        b.record(entity, "required", ids, f"Quarantined: {entity}.{column} is required.", "none")


def invalid_reference(b, rng, src, k):
    active = [p for p in src.state["products"] if p["status"] == "active"]
    customer_ids = [c["customer_id"] for c in src.state["customers"]]
    orders, items, payments = [], [], []
    for _ in range(k):
        ts = b.ts()
        oid = b.new_key("ORD")
        orders.append(b.emit("orders", {"order_id": oid, "customer_id": "CUST-X99999", "order_date": ts,
                                        "status": "pending"}, "insert", ts))
        product = rng.choice(active)
        b.emit("order_items", {"order_item_id": b.new_key("OI"), "order_id": oid, "product_id": product["product_id"],
                               "quantity": "1", "unit_price": product["price"]}, "insert", ts)

        ts = b.ts()
        oid = b.new_key("ORD")
        b.emit("orders", {"order_id": oid, "customer_id": rng.choice(customer_ids), "order_date": ts,
                          "status": "pending"}, "insert", ts)
        items.append(b.emit("order_items", {"order_item_id": b.new_key("OI"), "order_id": oid,
                                            "product_id": "PROD-X9999", "quantity": "1", "unit_price": "10.00"},
                            "insert", ts))

        ts = b.ts()
        payments.append(b.emit("payments", {"payment_id": b.new_key("PAY"), "order_id": "ORD-X9999999",
                                            "payment_type": "charge", "amount": "10.00", "method": "card",
                                            "status": "succeeded", "payment_at": ts}, "insert", ts))
    effect = "adds orphan rows to silver"
    behaviour = "Kept in silver and flagged by relationship tests, not quarantined: a parent may arrive in a later batch."
    b.record("orders", "foreign_key", orders, "Order for unknown customer CUST-X99999. " + behaviour, effect)
    b.record("order_items", "foreign_key", items, "Item for unknown product PROD-X9999. " + behaviour, effect)
    b.record("payments", "foreign_key", payments, "Payment for unknown order ORD-X9999999. " + behaviour, effect)


def negative_amount(b, rng, src, k):
    ids = [b.emit("payments", dict(p, amount="-" + p["amount"]), "update") for p in rng.sample(src.state["payments"], k)]
    b.record("payments", "range", ids, "Quarantined: amounts must be greater than zero; refunds use payment_type.", "none")


def payment_mismatch(b, rng, src, k):
    delivered = [o for o in src.state["orders"] if o["status"] == "delivered"]
    ids = []
    for order in rng.sample(delivered, k):
        ts = b.ts()
        b.emit("payments", {"payment_id": b.new_key("PAY"), "order_id": order["order_id"], "payment_type": "charge",
                            "amount": "5.00", "method": "card", "status": "succeeded", "payment_at": ts}, "insert", ts)
        ids.append(f"orders:{order['order_id']}")
    b.record("payments", "orders.paid_amount_matches", ids,
             "Valid rows, kept in silver. The order becomes overpaid by 5.00; the gold business test fails "
             "and reconciliation reports the order.", "adds payments; affected orders are overpaid")


def malformed_timestamp(b, rng, src, k):
    ids = [b.emit("orders", dict(o, order_date=BAD_TIMESTAMPS[i % len(BAD_TIMESTAMPS)]), "update")
           for i, o in enumerate(rng.sample(src.state["orders"], k))]
    b.record("orders", "type", ids, "Quarantined: order_date does not parse as an ISO 8601 UTC timestamp.", "none")


def malformed_type(b, rng, src, k):
    ids = [b.emit("order_items", dict(r, quantity=BAD_INTEGERS[i % len(BAD_INTEGERS)]), "update")
           for i, r in enumerate(rng.sample(src.state["order_items"], k))]
    b.record("order_items", "type", ids, "Quarantined: quantity is not an integer.", "none")
    ids = [b.emit("payments", dict(r, amount=BAD_DECIMALS[i % len(BAD_DECIMALS)]), "update")
           for i, r in enumerate(rng.sample(src.state["payments"], k))]
    b.record("payments", "type", ids, "Quarantined: amount is not a decimal with two places.", "none")


def schema_evolution(b, rng, src, k):
    for c in rng.sample(src.state["customers"], k):
        b.emit("customers", dict(c, loyalty_tier=rng.choice(["gold", "silver", "bronze"])), "update")
    b.headers["customers"] = header(src.contract, "customers") + ["loyalty_tier"]
    b.record("customers", "header", [f"{b.name}/customers.csv"],
             "Extra column loyalty_tier. Bronze captures it (new column or rescued data); silver ignores it "
             "until the contract adopts it. Row values are otherwise unchanged.",
             "source_updated_at advances; business values unchanged")


def late_arrival(b, rng, src, k):
    delivered = [o for o in src.state["orders"] if o["status"] == "delivered"]
    ids = []
    for o in rng.sample(delivered, k):
        older = fmt_ts(parse_ts(o["source_updated_at"]) - timedelta(hours=1))
        ids.append(b.emit("orders", dict(o, status="shipped"), "update", ts=older))
    b.record("orders", "late_arrival", ids,
             "Older version (status shipped, one hour before the current delivered version) arriving late. "
             "Silver ignores it; a last-file-wins job would wrongly apply it.", "none")


def replay(b, rng, src, k):
    already = {r["event_id"] for r in src.manifest["replays"]}
    candidates, seen = [], set()
    for i in range(1, src.manifest["config"]["batches"] + 1):
        _, rows = read_csv(src.root / batch_name(i) / "orders.csv")
        for row in rows:
            if row["event_id"] not in already and row["event_id"] not in seen:
                seen.add(row["event_id"])
                candidates.append(row)
    ids = []
    for row in rng.sample(candidates, k):
        b.files["orders"].append(dict(row))
        ids.append(row["event_id"])
    b.record("orders", "replay", ids, "Identical rows re-sent. Bronze stores them again; silver does not change.", "none")


SCENARIO_FUNCS = {
    "duplicate_key_conflict": duplicate_key_conflict, "null_required": null_required,
    "invalid_reference": invalid_reference, "negative_amount": negative_amount, "payment_mismatch": payment_mismatch,
    "malformed_timestamp": malformed_timestamp, "malformed_type": malformed_type, "schema_evolution": schema_evolution,
    "late_arrival": late_arrival, "replay": replay,
}


class Source:
    def __init__(self, root: Path, manifest: dict, contract: dict):
        self.root, self.manifest, self.contract = root, manifest, contract
        self.state = {e: read_csv(root / "_expected" / f"{e}.csv")[1] for e in ENTITIES}


def inject(source: Path, out: Path, scenarios, count: int = 5, seed: int = 7, force: bool = False) -> dict:
    """Write an anomalous copy of a clean dataset. Raises ValueError for invalid input."""
    source, out = Path(source), Path(out)
    unknown = set(scenarios) - set(SCENARIOS)
    if unknown:
        raise ValueError(f"unknown scenarios: {sorted(unknown)}; choose from {list(SCENARIOS)}")
    if not scenarios:
        raise ValueError("choose at least one scenario (--scenario NAME or --all)")
    if count < 1:
        raise ValueError("count must be at least 1")
    if not (source / "_manifest.json").exists() or not (source / "_expected").is_dir():
        raise ValueError(f"{source} is not a clean generated dataset (needs _manifest.json and _expected/)")
    if (source / "_anomaly_manifest.json").exists():
        raise ValueError(f"{source} already contains anomalies; inject into a copy of a clean dataset")
    if out.resolve() == source.resolve() or source.resolve() in out.resolve().parents:
        raise ValueError("--out must be outside the source dataset")
    manifest = read_json(source / "_manifest.json")
    contract = load_contract()
    first_batch = manifest["config"]["batches"] + 1
    if first_batch + len(SCENARIOS) > 1000:
        raise ValueError("too many batches in the source dataset to add scenario batches")

    prepare_out_dir(out, force)
    shutil.copytree(source, out, ignore=shutil.ignore_patterns("_expected"), dirs_exist_ok=True)
    src = Source(source, manifest, contract)
    as_of = midnight_utc(date.fromisoformat(manifest["config"]["as_of"]))

    batches, entries = {}, []
    for position, name in enumerate(SCENARIOS):
        if name not in scenarios:
            continue
        b = Batch(first_batch + position, as_of, name)
        SCENARIO_FUNCS[name](b, Rng(seed * 1000 + position), src, count)
        files = {}
        for entity in ENTITIES:
            if entity in b.files:
                path = out / b.name / f"{entity}.csv"
                write_csv(path, b.headers.get(entity, header(contract, entity)), b.files[entity])
                files[path.name] = {"rows": len(b.files[entity]), "sha256": sha256_file(path)}
        batches[b.name] = {"scenario": name, "window_start": fmt_ts(b.start), "files": files}
        entries += b.entries

    result = {"source": source.as_posix(), "seed": seed, "count": count,
              "scenarios": [s for s in SCENARIOS if s in scenarios], "batches": batches, "entries": entries}
    write_json(out / "_anomaly_manifest.json", result)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Add anomaly scenarios to a copy of a clean dataset.")
    parser.add_argument("--source", type=Path, default=Path("data/raw/clean"))
    parser.add_argument("--out", type=Path, default=Path("data/raw/anomalous"))
    parser.add_argument("--scenario", action="append", choices=SCENARIOS, default=[],
                        help="scenario to inject; repeat for several")
    parser.add_argument("--all", action="store_true", help="inject every scenario")
    parser.add_argument("--count", type=int, default=5, help="rows per scenario and entity (default: 5)")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--force", action="store_true", help="replace an existing output directory created by these tools")
    args = parser.parse_args(argv)
    try:
        result = inject(args.source, args.out, SCENARIOS if args.all else args.scenario, args.count, args.seed, args.force)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"Wrote {args.out} from {args.source}")
    for entry in result["entries"]:
        print(f"  {entry['batch']} {entry['scenario']:<23} {entry['entity']:<12} {entry['check']:<28} {entry['count']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
