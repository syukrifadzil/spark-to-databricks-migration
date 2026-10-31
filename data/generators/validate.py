"""Validate a generated dataset against the contract and its manifests.

Run from the repository root:

    python -m data.generators.validate --data data/raw/clean

Every check produces a set of observed identifiers (event ids, record keys or file paths).
Expectations come from the manifests: on a clean dataset, structural, relational and business
checks must observe nothing, and replays and late arrivals must match _manifest.json exactly.
On an anomalous dataset, every observation must match an entry in _anomaly_manifest.json.
Anything unexpected or missing fails validation with exit status 1.
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from data.generators.common import (
    ENTITIES, columns, header, load_contract, midnight_utc, parse_ts, primary_key, read_csv, read_json,
    sha256_file, window_index,
)

BUSINESS_RULES = ("orders.has_items", "orders.paid_amount_matches", "orders.cancelled_net_zero",
                  "orders.pending_not_fully_paid", "orders.refunds_within_charges", "orders.customer_before_order",
                  "payments.after_order", "customers.updated_after_created")
CHECKS = (
    [("structural", c) for c in ("integrity", "header", "required", "type", "domain", "range")]
    + [("delivery", c) for c in ("replay", "late_arrival", "event_conflict", "duplicate_event", "sequence_conflict")]
    + [("relational", "foreign_key")]
    + [("business", c) for c in BUSINESS_RULES]
    + [("state", "expected_state")]
)
PAID_STATUSES = ("paid", "shipped", "delivered")
DECIMAL_RE = re.compile(r"-?\d+\.\d{2}")
INTEGER_RE = re.compile(r"-?\d+")


@dataclass
class Report:
    data_dir: Path
    mode: str
    observed: dict = field(default_factory=lambda: defaultdict(set))
    expected: dict = field(default_factory=lambda: defaultdict(set))
    details: dict = field(default_factory=lambda: defaultdict(list))

    def flag(self, check: str, ident: str, detail: str = "") -> None:
        self.observed[check].add(ident)
        if detail:
            self.details[ident].append(detail)

    def checks(self) -> list[tuple[str, str]]:
        """Known checks, plus any check name a manifest mentions that the validator does not know."""
        known = {c for _, c in CHECKS}
        unknown = sorted((set(self.observed) | set(self.expected)) - known)
        return CHECKS + [("unknown", c) for c in unknown]

    def mismatches(self) -> dict:
        """check -> (unexpected ids, missing ids), only for checks that do not match."""
        out = {}
        for _, check in self.checks():
            unexpected = self.observed[check] - self.expected[check]
            missing = self.expected[check] - self.observed[check]
            if unexpected or missing:
                out[check] = (unexpected, missing)
        return out

    @property
    def ok(self) -> bool:
        return not self.mismatches()

    def summary(self, examples: int = 10) -> str:
        lines = [f"Validating {self.data_dir} ({self.mode} dataset)",
                 f"{'group':<11} {'check':<34} {'observed':>8} {'expected':>8}  status"]
        bad = self.mismatches()
        for group, check in self.checks():
            status = "FAIL" if check in bad else "ok"
            lines.append(f"{group:<11} {check:<34} {len(self.observed[check]):>8} {len(self.expected[check]):>8}  {status}")
        for check, (unexpected, missing) in bad.items():
            for label, ids in (("unexpected", unexpected), ("missing", missing)):
                for ident in sorted(ids)[:examples]:
                    detail = "; ".join(self.details.get(ident, []))
                    lines.append(f"  {check} {label}: {ident}" + (f" ({detail})" if detail else ""))
                if len(ids) > examples:
                    lines.append(f"  {check} {label}: ... {len(ids) - examples} more")
        lines.append("PASS: every observation matches the manifests" if self.ok else
                     f"FAIL: {len(bad)} check(s) do not match the manifests")
        return "\n".join(lines)


def parse_value(value: str, type_: str):
    if type_ == "string":
        return value
    if type_ == "timestamp":
        return parse_ts(value)
    if type_ == "decimal" and DECIMAL_RE.fullmatch(value):
        return Decimal(value)
    if type_ == "integer" and INTEGER_RE.fullmatch(value):
        return int(value)
    raise ValueError(f"not a {type_}")


def row_problems(row: dict, spec: list[dict], entity: str) -> list[tuple[str, str]]:
    """Structural problems as (check, rule) pairs. At most one problem per column."""
    problems = []
    for col in spec:
        name, value = col["name"], row.get(col["name"], "")
        rule = f"{entity}.{name}"
        if value == "":
            if col.get("required"):
                problems.append(("required", f"{rule}.required"))
            continue
        try:
            parsed = parse_value(value, col["type"])
        except ValueError:
            problems.append(("type", f"{rule}.type"))
            continue
        if ("allowed" in col and value not in col["allowed"]) or ("pattern" in col and not re.fullmatch(col["pattern"], value)):
            problems.append(("domain", f"{rule}.domain"))
        elif ("min" in col and parsed < Decimal(col["min"])) or ("min_exclusive" in col and parsed <= Decimal(col["min_exclusive"])):
            problems.append(("range", f"{rule}.range"))
    return problems


def _business_checks(report: Report, state: dict) -> None:
    orders, customers = state["orders"], state["customers"]
    total, charges, refunds, has_items = defaultdict(Decimal), defaultdict(Decimal), defaultdict(Decimal), set()
    for item in state["order_items"].values():
        total[item["order_id"]] += int(item["quantity"]) * Decimal(item["unit_price"])
        has_items.add(item["order_id"])
    for p in state["payments"].values():
        if p["status"] == "succeeded":
            (charges if p["payment_type"] == "charge" else refunds)[p["order_id"]] += Decimal(p["amount"])

    for oid, order in orders.items():
        ident, status = f"orders:{oid}", order["status"]
        paid, refunded = charges[oid], refunds[oid]
        if oid not in has_items:
            report.flag("orders.has_items", ident)
            continue
        if status in PAID_STATUSES and paid != total[oid]:
            report.flag("orders.paid_amount_matches", ident, f"status {status}, charges {paid}, total {total[oid]}")
        if status == "cancelled" and paid - refunded != 0:
            report.flag("orders.cancelled_net_zero", ident, f"net {paid - refunded}")
        if status == "pending" and paid >= total[oid]:
            report.flag("orders.pending_not_fully_paid", ident, f"charges {paid}, total {total[oid]}")
        if refunded > paid:
            report.flag("orders.refunds_within_charges", ident, f"refunds {refunded}, charges {paid}")
        customer = customers.get(order["customer_id"])
        if customer and customer["created_at"] > order["order_date"]:
            report.flag("orders.customer_before_order", ident)
    for pid, p in state["payments"].items():
        order = orders.get(p["order_id"])
        if order and p["payment_at"] < order["order_date"]:
            report.flag("payments.after_order", f"payments:{pid}")
    for cid, c in customers.items():
        if c["updated_at"] < c["created_at"]:
            report.flag("customers.updated_after_created", f"customers:{cid}")


def validate(data_dir: Path) -> Report:
    """Validate a dataset directory. Raises ValueError if it has no _manifest.json."""
    data_dir = Path(data_dir)
    if not (data_dir / "_manifest.json").exists():
        raise ValueError(f"{data_dir} has no _manifest.json; is it a generated dataset?")
    contract = load_contract()
    manifest = read_json(data_dir / "_manifest.json")
    anomaly_path = data_dir / "_anomaly_manifest.json"
    anomalies = read_json(anomaly_path) if anomaly_path.exists() else None
    report = Report(data_dir, "anomalous" if anomalies else "clean")
    as_of = midnight_utc(date.fromisoformat(manifest["config"]["as_of"]))

    # Expectations
    report.expected["late_arrival"] = {e["event_id"] for e in manifest["late_arrivals"]}
    report.expected["replay"] = {e["event_id"] for e in manifest["replays"]}
    hashes = {f"{b}/{name}": meta["sha256"] for b, batch in manifest["batches"].items() for name, meta in batch["files"].items()}
    if anomalies:
        for entry in anomalies["entries"]:
            report.expected[entry["check"]] |= set(entry["ids"])
        hashes.update({f"{b}/{name}": meta["sha256"] for b, batch in anomalies["batches"].items()
                       for name, meta in batch["files"].items()})

    # Integrity
    for rel, digest in sorted(hashes.items()):
        path = data_dir / rel
        if not path.exists() or sha256_file(path) != digest:
            report.flag("integrity", rel, "missing" if not path.exists() else "checksum differs")

    # Row and delivery checks, in delivery order
    specs = {e: contract["entities"][e]["columns"] + contract["feed_columns"] for e in ENTITIES}
    business = {e: columns(contract, e) for e in ENTITIES}
    seen_events, seen_sequence = {}, {}
    state = {e: {} for e in ENTITIES}
    for batch_dir in sorted(data_dir.glob("batch_[0-9][0-9][0-9]")):
        batch = int(batch_dir.name[6:])
        for entity in ENTITIES:
            path = batch_dir / f"{entity}.csv"
            if not path.exists():
                continue
            rel = f"{batch_dir.name}/{path.name}"
            head, rows = read_csv(path)
            expected_head = header(contract, entity)
            if head != expected_head:
                extra, missing = set(head) - set(expected_head), set(expected_head) - set(head)
                report.flag("header", rel, f"extra {sorted(extra)}, missing {sorted(missing)}")
            pk = primary_key(contract, entity)
            for line, row in enumerate(rows, start=2):
                eid = row.get("event_id", "")
                ident = eid or f"{rel}:{line}"
                problems = row_problems(row, specs[entity], entity)
                for check, rule in problems:
                    report.flag(check, ident, rule)

                full = tuple(row.get(c, "") for c in expected_head)
                if eid and eid in seen_events:
                    report.flag("replay" if seen_events[eid] == full else "event_conflict", eid, f"{rel}")
                    continue
                if eid:
                    seen_events[eid] = full
                if problems:
                    continue   # mirrors quarantine: invalid rows never reach the current state

                key, seq = row[pk], row["source_updated_at"]
                content = tuple(row[c] for c in business[entity])
                prior = seen_sequence.get((entity, key, seq))
                if prior is not None:
                    report.flag("duplicate_event" if prior == content else "sequence_conflict", eid,
                                f"{entity} {key} at {seq}")
                else:
                    seen_sequence[(entity, key, seq)] = content
                    if batch > window_index(parse_ts(seq), as_of):
                        report.flag("late_arrival", eid, f"{entity} {key} delivered in {batch_dir.name}")
                current = state[entity].get(key)
                if current is None or (seq, eid) > (current["source_updated_at"], current["event_id"]):
                    state[entity][key] = row

    # Relational checks on the current state
    for entity in ENTITIES:
        for col, parent in contract["entities"][entity]["foreign_keys"].items():
            for row in state[entity].values():
                if row[col] not in state[parent]:
                    report.flag("foreign_key", row["event_id"], f"{entity}.{col} {row[col]} not in {parent}")

    _business_checks(report, state)

    # Reconstructed state against the generator's ground truth (clean datasets only)
    if not anomalies:
        for entity in ENTITIES:
            path = data_dir / "_expected" / f"{entity}.csv"
            if not path.exists():
                report.flag("expected_state", f"_expected/{entity}.csv", "missing")
                continue
            head, rows = read_csv(path)
            pk = primary_key(contract, entity)
            truth = {r[pk]: r for r in rows}
            for key in sorted(truth.keys() | state[entity].keys()):
                actual, wanted = state[entity].get(key), truth.get(key)
                if actual is None or wanted is None or any(actual.get(c) != wanted[c] for c in head):
                    report.flag("expected_state", f"{entity}:{key}")
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Validate a generated retail dataset.")
    parser.add_argument("--data", type=Path, default=Path("data/raw/clean"), help="dataset directory")
    parser.add_argument("--examples", type=int, default=10, help="identifiers to print per failing check")
    args = parser.parse_args(argv)
    try:
        report = validate(args.data)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(report.summary(args.examples))
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
