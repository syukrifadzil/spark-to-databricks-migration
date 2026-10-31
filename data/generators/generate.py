"""Deterministic synthetic retail data: an initial snapshot plus incremental change-feed batches.

Run from the repository root:

    python -m data.generators.generate --preset small --out data/raw/clean

Every record is fictional. The same configuration and seed always produce byte-identical
files, because nothing depends on the current date, the locale or hash ordering.

Model: every entity change is a timestamped version. The snapshot (batch_000) holds the
latest version of each record before the as-of cut. Batch k holds every version produced
on day k after the cut, plus a few late arrivals (versions delayed to a later batch) and
replays (identical rows re-sent in a later batch). The true final state is written to
_expected/ so later phases can check that they reconstruct it.
"""
from __future__ import annotations

import argparse
import bisect
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from operator import itemgetter
from pathlib import Path

from data.generators.common import (
    DAY, ENTITIES, Rng, allowed, batch_name, columns, count_for, fmt_money, fmt_ts, header,
    load_contract, midnight_utc, money, prepare_out_dir, primary_key, sha256_file,
    window_index, write_csv, write_json,
)

PRESETS = {
    "tiny": dict(customers=40, products=15, orders=60, batch_customers=3, batch_orders=8, history_days=30),
    "small": dict(customers=500, products=50, orders=5_000, batch_customers=10, batch_orders=100, history_days=90),
    "medium": dict(customers=5_000, products=500, orders=50_000, batch_customers=50, batch_orders=1_000, history_days=90),
}

MASTER_DATA_DAYS = 730          # customers and products are created up to two years before the order history
TYPO_RATE = 0.05                # records created with a lower-case name, fixed later by a correction
PRE_SNAPSHOT_UPDATE_RATE = 0.20
CUSTOMER_UPDATE_RATE = 0.01     # per batch
PRICE_CHANGE_RATE = 0.02        # per batch
DISCONTINUE_RATE = 0.005        # per batch
INITIAL_DISCONTINUED_RATE = 0.08
FAILED_ATTEMPT_RATE = 0.10
SPLIT_PAYMENT_RATE = 0.05
RETURN_RATE = 0.05

# Illustrative weights for a plausible spread, not census data.
REGION_WEIGHTS = {"Selangor": 4, "Kuala Lumpur": 3, "Johor": 3}
METHOD_WEIGHTS = {"card": 45, "fpx": 30, "ewallet": 20, "bank_transfer": 5}
LINE_COUNTS = ([1, 2, 3, 4], [35, 35, 20, 10])
QUANTITIES = ([1, 2, 3, 4, 5], [60, 20, 10, 6, 4])
ORDER_PATHS = (["normal", "cancel_unpaid", "cancel_paid", "pending", "pending_partial"], [85, 5, 3, 5, 2])

# category: (min price, max price, product nouns)
CATEGORIES = {
    "groceries": (2, 60, ["Rice", "Flour", "Sugar", "Cooking Oil", "Noodles", "Sardines"]),
    "beverages": (2, 40, ["Coffee", "Tea", "Malted Drink", "Mineral Water", "Juice"]),
    "household": (3, 50, ["Detergent", "Dishwashing Liquid", "Tissue", "Floor Cleaner"]),
    "personal_care": (4, 80, ["Shampoo", "Body Wash", "Toothpaste", "Sunscreen"]),
    "electronics": (30, 1500, ["Headphones", "Power Bank", "Rice Cooker", "Electric Fan"]),
    "apparel": (15, 200, ["Baju Kurung", "T-Shirt", "Sandals", "Batik Shirt"]),
    "home_kitchen": (10, 300, ["Wok", "Food Container", "Kettle", "Bedsheet"]),
    "baby": (8, 150, ["Diapers", "Baby Wipes", "Formula Milk", "Baby Bottle"]),
    "stationery": (1, 30, ["Notebook", "Pen Set", "Colour Pencils", "Files"]),
    "sports": (10, 400, ["Badminton Racket", "Shuttlecock", "Football", "Yoga Mat"]),
}

FIRST_NAMES = ["Ahmad", "Aisyah", "Nurul", "Farah", "Hafiz", "Siti", "Amir", "Hidayah", "Wei Ling", "Jia Hui",
               "Kok Wai", "Mei Ling", "Jun Jie", "Xin Yi", "Arjun", "Priya", "Kavitha", "Ravi", "Suresh", "Divya",
               "Daniel", "Sarah", "Jason", "Michelle", "Adam", "Hannah", "Ethan", "Grace", "Irfan", "Alya"]
LAST_NAMES = ["Abdullah", "Ismail", "Rahman", "Hassan", "Yusof", "Ibrahim", "Tan", "Lim", "Lee", "Wong", "Ng",
              "Chong", "Teo", "Goh", "Raj", "Kumar", "Nair", "Pillai", "Menon", "Fernandez", "Gomez", "Anthony",
              "Joseph", "Chin", "Low", "Yap", "Osman", "Salleh", "Rao", "Das"]


@dataclass(frozen=True)
class Config:
    customers: int
    products: int
    orders: int
    batch_customers: int
    batch_orders: int
    history_days: int
    batches: int = 3
    seed: int = 42
    as_of: date = date(2026, 1, 1)
    late_rate: float = 0.01
    replay_rate: float = 0.01
    correction_rate: float = 0.002
    preset: str = "custom"

    def validate(self) -> None:
        problems = []
        for name in ("customers", "orders", "history_days", "batches"):
            if getattr(self, name) < 1:
                problems.append(f"{name} must be at least 1")
        for name in ("batch_customers", "batch_orders"):
            if getattr(self, name) < 0:
                problems.append(f"{name} must not be negative")
        if self.products < 4:
            problems.append("products must be at least 4 (an order has up to 4 distinct lines)")
        if self.batches > 999:
            problems.append("batches must be at most 999 (batch folders have three digits)")
        for name in ("late_rate", "replay_rate", "correction_rate"):
            if not 0 <= getattr(self, name) <= 1:
                problems.append(f"{name} must be between 0 and 1")
        if problems:
            raise ValueError("; ".join(problems))


@dataclass
class Version:
    ts: datetime
    entity: str
    key: str
    seq: int
    change_type: str
    row: dict
    event_id: str = ""


class History:
    """Every version of every record, in the order they were produced."""

    def __init__(self):
        self.versions: list[Version] = []
        self._last_ts: dict[tuple[str, str], datetime] = {}

    def add(self, entity: str, key: str, ts: datetime, change_type: str, row: dict) -> datetime:
        # Two versions of one record never share a timestamp, so clean data has no sequence ties.
        last = self._last_ts.get((entity, key))
        if last is not None and ts <= last:
            ts = last + timedelta(seconds=1)
        self._last_ts[(entity, key)] = ts
        row = dict(row, source_updated_at=fmt_ts(ts))
        if entity == "customers":
            row["updated_at"] = row["source_updated_at"]
        self.versions.append(Version(ts, entity, key, len(self.versions), change_type, row))
        return ts


# --- master data ---------------------------------------------------------------

def _customers(cfg, rng, h, regions, as_of, history_start, master_start):
    """Create customers and their changes. Returns (created_at list, id list), sorted by created_at."""
    weights = [REGION_WEIGHTS.get(r, 1) for r in regions]
    state, proper_name = {}, {}
    typos = set(rng.sample(range(1, cfg.customers + 1), count_for(cfg.customers, TYPO_RATE)))

    def new_customer(i, created, typo):
        first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
        cid = f"CUST-{i:06d}"
        proper_name[cid] = f"{first} {last}"
        local = f"{first}.{last}.{i}".lower().replace(" ", "")
        state[cid] = {"customer_id": cid, "name": proper_name[cid].lower() if typo else proper_name[cid],
                      "email": f"{local}@example.com", "region": rng.weighted(regions, weights),
                      "created_at": fmt_ts(created)}
        h.add("customers", cid, created, "insert", state[cid])
        return cid

    def change(cid):
        if rng.chance(0.5):
            state[cid]["region"] = rng.choice([r for r in regions if r != state[cid]["region"]])
        else:
            state[cid]["email"] = f"customer.{cid[5:]}.{rng.between(100, 999)}@example.org"

    for i in range(1, cfg.customers + 1):
        created = rng.seconds(master_start, history_start - DAY)
        cid = new_customer(i, created, i in typos)
        if rng.chance(PRE_SNAPSHOT_UPDATE_RATE):
            change(cid)
            h.add("customers", cid, rng.seconds(created + timedelta(seconds=1), as_of), "update", state[cid])

    to_correct = [f"CUST-{i:06d}" for i in sorted(typos)]
    next_id = cfg.customers + 1
    for k in range(1, cfg.batches + 1):
        w0 = as_of + (k - 1) * DAY
        w1 = w0 + DAY
        planned = []
        existing = sorted(state)
        for cid in rng.sample(existing, count_for(len(existing), CUSTOMER_UPDATE_RATE)):
            planned.append((rng.seconds(w0, w1), cid, "update"))
        fixes = to_correct[:count_for(cfg.customers, cfg.correction_rate)]
        to_correct = to_correct[len(fixes):]
        for cid in fixes:
            planned.append((rng.seconds(w0, w1), cid, "correction"))
        for _ in range(cfg.batch_customers):
            planned.append((rng.seconds(w0, w1), f"CUST-{next_id:06d}", "insert"))
            next_id += 1
        for ts, cid, kind in sorted(planned):
            if kind == "insert":
                new_customer(int(cid[5:]), ts, typo=False)
            elif kind == "update":
                change(cid)
                h.add("customers", cid, ts, "update", state[cid])
            else:
                state[cid]["name"] = proper_name[cid]
                h.add("customers", cid, ts, "correction", state[cid])

    ordered = sorted((row["created_at"], cid) for cid, row in state.items())
    return [c for c, _ in ordered], [cid for _, cid in ordered]


def _products(cfg, rng, h, categories, as_of, history_start, master_start):
    """Create products and their changes. Returns (always-active ids, price history per id)."""
    state, proper_name, history = {}, {}, {}
    discontinued = set(rng.sample(range(1, cfg.products + 1), round(cfg.products * INITIAL_DISCONTINUED_RATE)))
    typos = set(rng.sample(range(1, cfg.products + 1), count_for(cfg.products, TYPO_RATE)))
    for i in range(1, cfg.products + 1):
        pid = f"PROD-{i:05d}"
        created = rng.seconds(master_start, history_start - DAY)
        category = rng.choice(categories)
        low, high, nouns = CATEGORIES[category]
        price = Decimal(rng.between(low * 100, high * 100)) / 100
        proper_name[pid] = f"{rng.choice(nouns)} {rng.between(100, 999)}"
        state[pid] = {"product_id": pid, "product_name": proper_name[pid].lower() if i in typos else proper_name[pid],
                      "category": category, "price": fmt_money(price),
                      "status": "discontinued" if i in discontinued else "active"}
        history[pid] = [(created, price)]
        h.add("products", pid, created, "insert", state[pid])

    ever_discontinued = {f"PROD-{i:05d}" for i in discontinued}
    to_correct = [f"PROD-{i:05d}" for i in sorted(typos)]
    for k in range(1, cfg.batches + 1):
        w0 = as_of + (k - 1) * DAY
        w1 = w0 + DAY
        ids = sorted(state)
        planned = [(rng.seconds(w0, w1), pid, "price") for pid in rng.sample(ids, count_for(len(ids), PRICE_CHANGE_RATE))]
        active = [pid for pid in ids if state[pid]["status"] == "active"]
        planned += [(rng.seconds(w0, w1), pid, "discontinue")
                    for pid in rng.sample(active, round(cfg.products * DISCONTINUE_RATE))]
        fixes = to_correct[:count_for(cfg.products, cfg.correction_rate)]
        to_correct = to_correct[len(fixes):]
        planned += [(rng.seconds(w0, w1), pid, "correction") for pid in fixes]
        for ts, pid, kind in sorted(planned):
            if kind == "price":
                price = money(history[pid][-1][1] * rng.between(90, 115) / 100)
                state[pid]["price"] = fmt_money(price)
                ts = h.add("products", pid, ts, "update", state[pid])
                history[pid].append((ts, price))
            elif kind == "discontinue":
                state[pid]["status"] = "discontinued"
                ever_discontinued.add(pid)
                h.add("products", pid, ts, "update", state[pid])
            else:
                state[pid]["product_name"] = proper_name[pid]
                h.add("products", pid, ts, "correction", state[pid])

    always_active = [pid for pid in sorted(state) if pid not in ever_discontinued]
    if not always_active:
        raise ValueError("no product stays active; increase products")
    return always_active, history


def _price_at(history, ts):
    times = [t for t, _ in history]
    return history[bisect.bisect_right(times, ts) - 1][1]


# --- orders, items, payments -----------------------------------------------------

def _orders(cfg, rng, h, customers, products, methods, as_of, history_start):
    created_at, customer_ids = customers
    active, price_history = products
    method_weights = [METHOD_WEIGHTS[m] for m in methods]
    counters = {"order": 0, "item": 0, "payment": 0}

    def next_id(kind, prefix, width):
        counters[kind] += 1
        return f"{prefix}-{counters[kind]:0{width}d}"

    def place(placed: datetime) -> None:
        oid = next_id("order", "ORD", 7)
        eligible = bisect.bisect_left(created_at, fmt_ts(placed))
        order = {"order_id": oid, "customer_id": customer_ids[rng.below(eligible)],
                 "order_date": fmt_ts(placed), "status": "pending"}
        h.add("orders", oid, placed, "insert", order)

        total, line_totals = Decimal(0), []
        for pid in rng.sample(active, rng.weighted(*LINE_COUNTS)):
            quantity, price = rng.weighted(*QUANTITIES), _price_at(price_history[pid], placed)
            iid = next_id("item", "OI", 8)
            h.add("order_items", iid, placed, "insert",
                  {"order_item_id": iid, "order_id": oid, "product_id": pid, "quantity": str(quantity),
                   "unit_price": fmt_money(price)})
            line_totals.append(quantity * price)
            total += quantity * price

        method = rng.weighted(methods, method_weights)

        def pay(payment_type, amount, status, ts):
            pid = next_id("payment", "PAY", 8)
            h.add("payments", pid, ts, "insert",
                  {"payment_id": pid, "order_id": oid, "payment_type": payment_type, "amount": fmt_money(amount),
                   "method": method, "status": status, "payment_at": fmt_ts(ts)})

        def set_status(status, ts):
            order["status"] = status
            h.add("orders", oid, ts, "update", order)

        def part_of_total():
            part = money(total * rng.between(20, 80) / 100)
            return part if 0 < part < total else None

        path = rng.weighted(*ORDER_PATHS)
        t1 = placed + timedelta(minutes=rng.between(1, 60))
        if path == "normal":
            if rng.chance(FAILED_ATTEMPT_RATE):
                pay("charge", total, "failed", rng.seconds(placed, t1))
            part = part_of_total() if rng.chance(SPLIT_PAYMENT_RATE) else None
            if part is None:
                paid = t1
                pay("charge", total, "succeeded", paid)
            else:
                paid = t1 + timedelta(minutes=rng.between(1, 30))
                pay("charge", part, "succeeded", t1)
                pay("charge", total - part, "succeeded", paid)
            set_status("paid", paid)
            shipped = paid + timedelta(hours=rng.between(12, 48))
            set_status("shipped", shipped)
            delivered = shipped + timedelta(hours=rng.between(24, 120))
            set_status("delivered", delivered)
            if rng.chance(RETURN_RATE):
                pay("refund", rng.choice(line_totals), "succeeded", delivered + timedelta(hours=rng.between(24, 168)))
        elif path == "cancel_unpaid":
            set_status("cancelled", placed + timedelta(hours=rng.between(1, 48)))
        elif path == "cancel_paid":
            pay("charge", total, "succeeded", t1)
            set_status("paid", t1)
            cancelled = t1 + timedelta(hours=rng.between(1, 24))
            set_status("cancelled", cancelled)
            pay("refund", total, "succeeded", cancelled)   # same instant, so no cut can split them
        elif path == "pending":
            if rng.chance(0.5):
                pay("charge", total, "failed", t1)
        else:  # pending_partial
            part = part_of_total()
            if part is not None:
                pay("charge", part, "succeeded", t1)

    for placed in sorted(rng.seconds(history_start, as_of) for _ in range(cfg.orders)):
        place(placed)
    for k in range(1, cfg.batches + 1):
        w0 = as_of + (k - 1) * DAY
        for placed in sorted(rng.seconds(w0, w0 + DAY) for _ in range(cfg.batch_orders)):
            place(placed)


# --- delivery ----------------------------------------------------------------------

def _deliver(cfg, rng, h, contract, as_of):
    end = as_of + cfg.batches * DAY
    versions = sorted(h.versions, key=lambda v: (v.ts, ENTITIES.index(v.entity), v.key, v.seq))
    for i, v in enumerate(versions, start=1):
        v.event_id = f"EVT-{i:08d}"

    snapshot, deliveries, final = {}, [], {}
    for v in versions:
        if v.ts >= end:
            continue
        final[(v.entity, v.key)] = v
        if v.ts < as_of:
            snapshot[(v.entity, v.key)] = v
        else:
            deliveries.append([window_index(v.ts, as_of), v])

    late = []
    candidates = [d for d in deliveries if d[0] < cfg.batches]
    for d in rng.sample(candidates, count_for(len(candidates), cfg.late_rate)):
        window = d[0]
        d[0] = rng.between(window + 1, cfg.batches)
        late.append({"event_id": d[1].event_id, "entity": d[1].entity, "key": d[1].key,
                     "window_batch": batch_name(window), "delivered_in": batch_name(d[0])})

    rows = [(0, v.entity, dict(v.row, change_type="snapshot", batch_id=batch_name(0), event_id=v.event_id))
            for v in snapshot.values()]
    rows += [(b, v.entity, dict(v.row, change_type=v.change_type, batch_id=batch_name(b), event_id=v.event_id))
             for b, v in deliveries]

    replays = []
    candidates = [r for r in rows if 1 <= r[0] < cfg.batches]
    for b, entity, row in rng.sample(candidates, count_for(len(candidates), cfg.replay_rate)):
        target = rng.between(b + 1, cfg.batches)
        rows.append((target, entity, dict(row)))
        replays.append({"event_id": row["event_id"], "entity": entity, "key": row[primary_key(contract, entity)],
                        "original_batch": batch_name(b), "replayed_in": batch_name(target)})

    files = {}
    for b, entity, row in rows:
        files.setdefault((b, entity), []).append(row)
    for file_rows in files.values():
        file_rows.sort(key=lambda r: (r["source_updated_at"], r["event_id"]))

    expected = {entity: [] for entity in ENTITIES}
    for (entity, key), v in sorted(final.items()):
        expected[entity].append(dict(v.row, event_id=v.event_id))

    corrections = [{"event_id": v.event_id, "entity": v.entity, "key": v.key,
                    "window_batch": batch_name(window_index(v.ts, as_of))}
                   for v in versions if v.change_type == "correction" and as_of <= v.ts < end]
    by_event = itemgetter("event_id")
    return {"files": files, "expected": expected, "late_arrivals": sorted(late, key=by_event),
            "replays": sorted(replays, key=by_event), "corrections": corrections}


# --- public entry points -----------------------------------------------------------

def generate(cfg: Config, contract: dict) -> dict:
    """Build the whole dataset in memory. Raises ValueError for an invalid configuration."""
    cfg.validate()
    methods = allowed(contract, "payments", "method")
    categories = allowed(contract, "products", "category")
    if set(methods) != set(METHOD_WEIGHTS) or set(categories) != set(CATEGORIES):
        raise ValueError("generator constants are out of date with data/contracts/retail_contract.json")
    rng = Rng(cfg.seed)
    as_of = midnight_utc(cfg.as_of)
    history_start = as_of - cfg.history_days * DAY
    master_start = history_start - MASTER_DATA_DAYS * DAY
    h = History()
    customers = _customers(cfg, rng, h, allowed(contract, "customers", "region"), as_of, history_start, master_start)
    products = _products(cfg, rng, h, categories, as_of, history_start, master_start)
    _orders(cfg, rng, h, customers, products, methods, as_of, history_start)
    return _deliver(cfg, rng, h, contract, as_of)


def write_output(result: dict, cfg: Config, contract: dict, out: Path, force: bool = False) -> dict:
    """Write batches, expected state and _manifest.json. Returns the manifest."""
    prepare_out_dir(out, force)
    as_of = midnight_utc(cfg.as_of)
    batches = {}
    for b in range(cfg.batches + 1):
        name = batch_name(b)
        files = {}
        for entity in ENTITIES:
            path = out / name / f"{entity}.csv"
            rows = result["files"].get((b, entity), [])
            write_csv(path, header(contract, entity), rows)
            files[path.name] = {"rows": len(rows), "sha256": sha256_file(path)}
        window = ({"type": "snapshot", "state_before": fmt_ts(as_of)} if b == 0 else
                  {"type": "change_feed", "window_start": fmt_ts(as_of + (b - 1) * DAY), "window_end": fmt_ts(as_of + b * DAY)})
        batches[name] = dict(window, files=files)

    for entity in ENTITIES:
        write_csv(out / "_expected" / f"{entity}.csv",
                  columns(contract, entity) + ["source_updated_at", "event_id"], result["expected"][entity])

    manifest = {
        "contract_version": contract["version"],
        "config": dict(asdict(cfg), as_of=cfg.as_of.isoformat()),
        "batches": batches,
        "expected_rows": {entity: len(result["expected"][entity]) for entity in ENTITIES},
        "late_arrivals": result["late_arrivals"],
        "replays": result["replays"],
        "corrections": result["corrections"],
    }
    write_json(out / "_manifest.json", manifest)
    return manifest


def run(cfg: Config, out: Path, force: bool = False) -> dict:
    contract = load_contract()
    return write_output(generate(cfg, contract), cfg, contract, out, force)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic synthetic retail CSVs.")
    parser.add_argument("--preset", choices=sorted(PRESETS), default="medium",
                        help="size preset (default: medium); individual counts below override it")
    for name in PRESETS["medium"]:
        parser.add_argument(f"--{name.replace('_', '-')}", type=int, help=f"override the preset's {name}")
    parser.add_argument("--batches", type=int, default=3, help="incremental batches after the snapshot (default: 3)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--as-of", type=date.fromisoformat, default=date(2026, 1, 1),
                        help="snapshot cut-off date, midnight UTC (default: 2026-01-01)")
    parser.add_argument("--late-rate", type=float, default=0.01, help="share of batch events delivered late")
    parser.add_argument("--replay-rate", type=float, default=0.01, help="share of batch rows re-sent later")
    parser.add_argument("--correction-rate", type=float, default=0.002, help="corrections per batch, as a share of records")
    parser.add_argument("--out", type=Path, default=Path("data/raw/clean"))
    parser.add_argument("--force", action="store_true", help="replace an existing output directory created by this tool")
    args = parser.parse_args(argv)

    sizes = dict(PRESETS[args.preset])
    sizes.update({k: getattr(args, k) for k in sizes if getattr(args, k) is not None})
    try:
        cfg = Config(**sizes, batches=args.batches, seed=args.seed, as_of=args.as_of, late_rate=args.late_rate,
                     replay_rate=args.replay_rate, correction_rate=args.correction_rate, preset=args.preset)
        manifest = run(cfg, args.out, args.force)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"Wrote {args.out} (preset {cfg.preset}, seed {cfg.seed}, as-of {cfg.as_of})")
    for name, batch in manifest["batches"].items():
        counts = ", ".join(f"{f[:-4]}={meta['rows']}" for f, meta in batch["files"].items())
        print(f"  {name}: {counts}")
    print(f"  expected final rows: {manifest['expected_rows']}")
    print(f"  late arrivals: {len(manifest['late_arrivals'])}, replays: {len(manifest['replays'])}, "
          f"corrections: {len(manifest['corrections'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
