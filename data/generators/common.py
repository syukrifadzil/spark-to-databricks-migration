"""Helpers shared by the generator, the anomaly injector and the validator."""
from __future__ import annotations

import csv
import hashlib
import json
import random
import shutil
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

CONTRACT_PATH = Path(__file__).resolve().parent.parent / "contracts" / "retail_contract.json"
ENTITIES = ("customers", "products", "orders", "order_items", "payments")
TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
DAY = timedelta(days=1)
CENT = Decimal("0.01")


# --- contract -------------------------------------------------------------

def load_contract(path: Path = CONTRACT_PATH) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def columns(contract: dict, entity: str) -> list[str]:
    """Business columns of an entity, in CSV order."""
    return [c["name"] for c in contract["entities"][entity]["columns"]]


def header(contract: dict, entity: str) -> list[str]:
    """Full CSV header: business columns followed by feed metadata columns."""
    return columns(contract, entity) + [c["name"] for c in contract["feed_columns"]]


def allowed(contract: dict, entity: str, column: str) -> list[str]:
    return next(c["allowed"] for c in contract["entities"][entity]["columns"] if c["name"] == column)


def primary_key(contract: dict, entity: str) -> str:
    return contract["entities"][entity]["primary_key"]


# --- money and time ----------------------------------------------------------

def money(value) -> Decimal:
    """Round to cents, half-up, matching Spark round(). Python's decimal default is half-even."""
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def fmt_money(value: Decimal) -> str:
    return f"{money(value):.2f}"


def fmt_ts(ts: datetime) -> str:
    return ts.strftime(TS_FORMAT)


def parse_ts(text: str) -> datetime:
    return datetime.strptime(text, TS_FORMAT).replace(tzinfo=timezone.utc)


def midnight_utc(day) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=timezone.utc)


def batch_name(index: int) -> str:
    return f"batch_{index:03d}"


def window_index(ts: datetime, as_of: datetime) -> int:
    """Batch a timestamp belongs to: 0 for the snapshot (before as_of), k for day k after as_of."""
    return 0 if ts < as_of else (ts - as_of) // DAY + 1


# --- randomness --------------------------------------------------------------

class Rng:
    """Seeded randomness built only on random.random().

    Python guarantees that random() returns the same sequence for the same seed across
    versions; helpers such as choice() and sample() carry no such guarantee, so they are
    reimplemented here on top of random().
    """

    def __init__(self, seed: int):
        self._random = random.Random(seed).random

    def random(self) -> float:
        return self._random()

    def below(self, n: int) -> int:
        return min(int(self._random() * n), n - 1)

    def between(self, low: int, high: int) -> int:
        """Integer in [low, high], both inclusive."""
        return low + self.below(high - low + 1)

    def chance(self, p: float) -> bool:
        return self._random() < p

    def choice(self, seq):
        return seq[self.below(len(seq))]

    def weighted(self, items, weights):
        x = self._random() * sum(weights)
        for item, weight in zip(items, weights):
            x -= weight
            if x < 0:
                return item
        return items[-1]

    def sample(self, seq, k: int) -> list:
        """k distinct elements, partial Fisher-Yates over a copy."""
        pool = list(seq)
        k = min(k, len(pool))
        for i in range(k):
            j = i + self.below(len(pool) - i)
            pool[i], pool[j] = pool[j], pool[i]
        return pool[:k]

    def seconds(self, start: datetime, end: datetime) -> datetime:
        """Whole-second timestamp in [start, end)."""
        span = int((end - start).total_seconds())
        return start if span <= 0 else start + timedelta(seconds=self.below(span))


def count_for(n: int, rate: float) -> int:
    """Number of items to select at a rate: zero only when the rate or population is zero."""
    return 0 if rate == 0 or n == 0 else max(1, round(n * rate))


# --- files -------------------------------------------------------------------

def write_csv(path: Path, columns_: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(columns_)
        writer.writerows([[row.get(c, "") for c in columns_] for row in rows])


def read_csv(path: Path) -> tuple[list[str], list[dict]]:
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        head = next(reader, [])
        return head, [dict(zip(head, values)) for values in reader]


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare_out_dir(out: Path, force: bool) -> None:
    """Create an empty output directory.

    An existing non-empty directory is replaced only with force, and only if it holds a
    _manifest.json, i.e. it was produced by these tools. Anything else is left alone.
    """
    if out.exists() and any(out.iterdir()):
        if not force:
            raise ValueError(f"{out} is not empty; pass --force to replace it")
        if not (out / "_manifest.json").exists():
            raise ValueError(f"refusing to delete {out}: it has no _manifest.json, so it was not created by these tools")
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
