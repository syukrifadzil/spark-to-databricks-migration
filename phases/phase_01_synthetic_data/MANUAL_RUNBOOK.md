# Phase 01 Manual Runbook: Synthetic Data

All steps are run by the maintainer. None of these commands have been run by the author of the code, so the expected outputs below describe what the code is written to produce. Record what you actually see in `HANDOFF.md`.

Working directory for every step: the repository root.

```bash
cd ~/Desktop/databricks-prep/dbx-proj/spark-to-dbx
```

Nothing in this phase touches Databricks.

## Step 1. Check Python

```bash
python3 --version
```

Expected: `Python 3.10.x` or later.

If it is older (macOS Command Line Tools ship an older Python 3), install a newer one and use it explicitly:

```bash
brew install python@3.12
python3.12 --version
```

In that case, use `python3.12` instead of `python3` in Step 2.

## Step 2. Create the virtual environment and install pytest

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python --version
python -m pytest --version
```

Expected:
- The prompt shows `(.venv)`.
- `python --version` matches Step 1.
- `pytest --version` prints `pytest 8.x` or later.
- `.venv/` is git-ignored.

Every later step assumes the virtual environment is active. In a new terminal, run `source .venv/bin/activate` again.

## Step 3. First run on the tiny preset

```bash
python -m data.generators.generate --preset tiny --out data/raw/tiny
```

Expected output shape (`n` marks counts that depend on the seed; they are fixed for seed 42 but I cannot predict them without running the code):

```
Wrote data/raw/tiny (preset tiny, seed 42, as-of 2026-01-01)
  batch_000: customers=40, products=15, orders=60, order_items=n, payments=n
  batch_001: customers=n, products=n, orders=n, order_items=n, payments=n
  batch_002: ...
  batch_003: ...
  expected final rows: {'customers': 49, 'products': 15, 'orders': 84, 'order_items': n, 'payments': n}
  late arrivals: n, replays: n, corrections: n
```

Exact by design:
- `batch_000` customers 40, products 15, orders 60
- final customers 49, products 15, orders 84
- late arrivals, replays and corrections at least 1 each

Approximate: order items should be roughly twice the order count.

Then validate:

```bash
python -m data.generators.validate --data data/raw/tiny
```

Expected:
- A table with one line per check.
- Every status is `ok`.
- `replay` and `late_arrival` show equal observed and expected counts, at least 1 each.
- Every other check shows 0 and 0.
- The last line is `PASS: every observation matches the manifests`.
- Exit status 0. Confirm with `echo $?` right after the command.

## Step 4. Run the unit tests

```bash
python -m pytest -q
```

Expected: `30 passed`. The tests use the tiny preset in temporary directories and write nothing into the repository.

Save the full output for `HANDOFF.md`. If anything fails, run `python -m pytest -q -x` to stop at the first failure and paste that output to me.

## Step 5. Check reproducibility

```bash
python -m data.generators.generate --preset small --out data/raw/check_a
python -m data.generators.generate --preset small --out data/raw/check_b
diff -r data/raw/check_a data/raw/check_b && echo IDENTICAL
shasum -a 256 data/raw/check_a/_manifest.json data/raw/check_b/_manifest.json
```

Expected:
- `diff` prints nothing, followed by `IDENTICAL`.
- The two manifest checksums are equal.

Then check that the seed matters:

```bash
python -m data.generators.generate --preset small --seed 43 --out data/raw/check_c
diff -rq data/raw/check_a data/raw/check_c | head -5
```

Expected: several `Files ... differ` lines.

Clean up. This is destructive: it deletes only these three generated folders under the git-ignored `data/raw/`.

```bash
rm -rf data/raw/check_a data/raw/check_b data/raw/check_c
```

## Step 6. Generate the working datasets

The small preset is the default for Phase 02 and 03 development. Medium matches the brief's full sizes.

```bash
time python -m data.generators.generate --preset small --out data/raw/clean
python -m data.generators.validate --data data/raw/clean

time python -m data.generators.generate --preset medium --out data/raw/medium
python -m data.generators.validate --data data/raw/medium
```

Expected:
- small: `batch_000` has customers=500, products=50, orders=5000. Final customers 530, orders 5300.
- medium: `batch_000` has customers=5000, products=500, orders=50000. Final customers 5150, orders 53000.
- Both validations end with `PASS`.

Record the `real` time printed by `time` for both runs, and the folder sizes:

```bash
du -sh data/raw/clean data/raw/medium
```

These are the only performance numbers this phase produces. Do not compare them across machines.

## Step 7. Inject anomalies

All scenarios at once:

```bash
python -m data.generators.inject_anomalies --source data/raw/clean --out data/raw/anomalous --all
python -m data.generators.validate --data data/raw/anomalous
```

Expected from the injector:
- One line per scenario and entity, in batches `batch_004` to `batch_013`.
- Counts of 5, except `schema_evolution` (1 file).
- Payment mismatch and late arrival counts can be below 5 only if there are fewer than 5 delivered orders, which is not expected for small.

Expected from the validator:
- `PASS`.
- The `required`, `type`, `range`, `foreign_key`, `sequence_conflict`, `header` and `orders.paid_amount_matches` checks show non-zero observed counts equal to their expected counts.

One scenario alone, to see isolation:

```bash
python -m data.generators.inject_anomalies --source data/raw/clean --out data/raw/only_nulls --scenario null_required
python -m data.generators.validate --data data/raw/only_nulls
```

Expected:
- One batch, `batch_005`. Its position in the scenario list fixes the batch number, so `batch_004` does not exist here.
- `PASS`.

Confirm the clean dataset was not touched:

```bash
python -m data.generators.validate --data data/raw/clean
```

Expected: still `PASS`. The integrity check would fail if any clean file had changed.

## Step 8. Inspect the data

```bash
head -3 data/raw/clean/batch_000/orders.csv
head -3 data/raw/clean/batch_001/payments.csv
python -m json.tool data/raw/clean/_manifest.json | head -40
python -m json.tool data/raw/anomalous/_anomaly_manifest.json | head -40
```

Expected:
- Headers match `docs/data_contracts.md` section 4: business columns, then `source_updated_at,change_type,batch_id,event_id`.
- Timestamps look like `2025-11-14T08:31:07Z`; amounts like `123.45`.
- Emails are on `example.com` or `example.org`.

Check by eye that names, regions and categories look sensible and that nothing resembles real personal data.

## Step 9. Create the committed samples

Small, reproducible samples let reviewers read real files on GitHub:

```bash
python -m data.generators.generate --preset tiny --out data/samples/clean
python -m data.generators.inject_anomalies --source data/samples/clean --out data/samples/anomalous --all --count 3
python -m data.generators.validate --data data/samples/clean
python -m data.generators.validate --data data/samples/anomalous
du -sh data/samples
```

Expected:
- Both validations `PASS`.
- `data/samples` is well under 1 MB.

If you rerun later, add `--force`. It replaces only folders that contain a `_manifest.json`.

## Step 10. Commit and push

```bash
git status --short
```

Expected:
- New: `data/__init__.py`, `data/contracts/`, `data/generators/`, `data/samples/`, `tests/`, `pyproject.toml`, `requirements-dev.txt`, `docs/diagrams/data-model.svg`, `docs/diagrams/data-generation-flow.svg`.
- Modified: `README.md`, `docs/architecture.md`, `docs/data_contracts.md`, `docs/diagrams/phase-plan.svg`, `phases/phase_00_foundation/HANDOFF.md`, and the four Phase 01 documents.
- **No `data/raw/`, `.venv/`, `__pycache__/` or `.pytest_cache/` entries.**

```bash
git add data/__init__.py data/contracts data/generators data/samples tests pyproject.toml requirements-dev.txt \
        README.md docs phases
git status --short | grep -E 'data/raw|\.venv|__pycache__|\.pytest_cache' || echo "no generated or local files staged"
git diff --cached --name-only | wc -l
git diff --cached | grep -nE 'dapi[0-9a-zA-Z]{16,}|DATABRICKS_TOKEN=[A-Za-z0-9]|https://[^[:space:]<]*databricks\.com'
git commit -m "feat(data): implement reproducible retail data generator"
git push
```

Expected:
- The `grep -E` line prints `no generated or local files staged`.
- The secret scan prints nothing.
- The push reports `main -> main`.

If `data/raw` shows up, unstage it with `git restore --staged data/raw` and check `.gitignore`.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'data'` | Not run from the repository root, or run as a script path | `cd` to the root; use `python -m data.generators.generate`, not `python data/generators/generate.py` |
| Import or syntax errors on Python older than 3.10 | Unsupported Python version | Step 1 |
| `error: data/raw/... is not empty; pass --force` | Output folder exists | Add `--force`, or choose a new `--out` |
| `refusing to delete ...: it has no _manifest.json` | `--out` points at a folder these tools did not create | Choose another folder; nothing was deleted |
| `error: ... is not a clean generated dataset` | Injector source is missing `_expected/` or is itself anomalous | Point `--source` at a generator output |
| Validator `FAIL` on a clean dataset | A bug, or a file edited by hand | Paste the full report; `integrity` failures mean a file changed after generation |
| `pytest: command not found` | Virtual environment not active | `source .venv/bin/activate` |
| Medium preset very slow or memory-hungry | Plain Python loops over about 400,000 versions | Record time and memory (Activity Monitor); use small for day-to-day work |

## Cleanup (destructive)

Deletes all generated data under the git-ignored `data/raw/`. Committed samples are not affected.

```bash
rm -rf data/raw
```
