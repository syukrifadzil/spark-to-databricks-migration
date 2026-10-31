# Phase 02 Manual Runbook: Legacy PySpark Job

All steps are run by the maintainer. None of these commands have been run by the author. Record actual output in `HANDOFF.md`.

Working directory for every step is the repository root, with the virtual environment active:

```bash
cd ~/Desktop/databricks-prep/dbx-proj/spark-to-dbx
source .venv/bin/activate
```

Prerequisite: the Phase 01 datasets exist (`data/raw/clean`, `data/raw/medium`, `data/raw/anomalous`) and `data/samples/` is committed. Nothing in this phase touches Databricks.

## Step 1. Java

```bash
java -version
```

Expected: `openjdk version "17..."` or `"21..."`.

If it says `Unable to locate a Java Runtime`, or shows a version below 17, install Java 17:

```bash
brew install openjdk@17
export JAVA_HOME="$(brew --prefix openjdk@17)"
export PATH="$JAVA_HOME/bin:$PATH"
java -version
```

Expected: `openjdk version "17.x.x"`.

The two `export` lines last only for this terminal. To keep them, add them to `~/.zshrc`:

```bash
echo 'export JAVA_HOME="$(brew --prefix openjdk@17)"' >> ~/.zshrc
echo 'export PATH="$JAVA_HOME/bin:$PATH"' >> ~/.zshrc
```

Homebrew may also print a `sudo ln -sfn ...` command so that macOS tools can find this JDK. That is optional for this project; PySpark uses `JAVA_HOME`.

## Step 2. Install PySpark

```bash
python -m pip install -r requirements-spark.txt
python -c "import pyspark; print(pyspark.__version__)"
```

Expected: a 4.x version.

If the install or the import fails on Python 3.15, create a separate environment on Python 3.12 and use it for the rest of this phase:

```bash
deactivate
brew install python@3.12
python3.12 -m venv .venv-spark
source .venv-spark/bin/activate
python -m pip install -r requirements-dev.txt -r requirements-spark.txt
python -c "import pyspark; print(pyspark.__version__)"
```

`.venv-spark/` is git-ignored. Tell me which environment you used.

## Step 3. Spark smoke test

```bash
python -c "from pyspark.sql import SparkSession; s = SparkSession.builder.master('local[1]').getOrCreate(); print('rows:', s.range(3).count()); s.stop()"
```

Expected:
- Some `WARN` lines, then `rows: 3`.
- Warnings such as `NativeCodeLoader: Unable to load native-hadoop library` or `Your hostname resolves to a loopback address` are harmless.

## Step 4. Tests

```bash
python -m pytest -q
```

Expected: `34 passed` (30 from Phase 01 plus 4 legacy-job tests). They take longer than before because Spark starts twice.

If PySpark or Java is missing, the legacy module is skipped instead: `30 passed, 1 skipped`.

Paste any failure in full.

## Step 5. Run on the committed tiny samples

```bash
python -m legacy_spark.retail_nightly_job --input data/samples/clean --output output/legacy/samples
ls output/legacy/samples
head -5 output/legacy/samples/daily_sales/part-*.csv
cat output/legacy/samples/baseline_metrics.json
```

Expected:
- Log lines with timestamps:
  - `start ...`
  - `read customers: N rows from 4 files`, and the same for the other four entities
  - `wrote daily_sales`, `wrote customer_lifetime_value`, `wrote product_performance`
  - `done in X s`
- `ls` shows `baseline_metrics.json`, `customer_lifetime_value`, `daily_sales`, `product_performance`.
- The daily sales header is `business_date,orders_placed,orders_sold,items_sold,gross_sales,charges,refunds,net_payments`.
- In the metrics:
  - `customer_lifetime_value.rows` is `49.00`
  - `product_performance.rows` is `15.00`
  - `daily_sales.null_business_date_rows` is `0.00`
  - the three gross sales metrics are equal

## Step 6. Run on the small and medium datasets

```bash
time python -m legacy_spark.retail_nightly_job --input data/raw/clean --output output/legacy/clean
time python -m legacy_spark.retail_nightly_job --input data/raw/medium --output output/legacy/medium
python -m json.tool output/legacy/clean/baseline_metrics.json
python -m json.tool output/legacy/medium/baseline_metrics.json
```

Expected: both complete. Record:
- the `real` time
- `duration_seconds` and `spark_version` from each JSON
- the metrics

`customer_lifetime_value.rows` should be `530.00` (small) and `5150.00` (medium); `product_performance.rows` `50.00` and `500.00`.

These are the legacy baseline numbers for Phase 06 and 07. They come from this run on this machine only. Do not compare them with Databricks timings.

## Step 7. Run on the anomalous dataset and compare

```bash
python -m legacy_spark.retail_nightly_job --input data/raw/anomalous --output output/legacy/anomalous
python - <<'EOF'
import json
clean = json.load(open("output/legacy/clean/baseline_metrics.json"))["metrics"]
anomalous = json.load(open("output/legacy/anomalous/baseline_metrics.json"))["metrics"]
for key in sorted(clean):
    flag = "" if clean[key] == anomalous.get(key) else "  <- differs"
    print(f"{key:48} {clean[key]:>14} {anomalous.get(key):>14}{flag}")
EOF
```

Expected:
- The job completes. Schema evolution does not crash it (L6).
- Several metrics differ, for example `daily_sales.charges` and `daily_sales.null_business_date_rows`.

Compare the differences with the table in `EXPLANATION.md` section 5 and note any that do not match the prediction. That table is a prediction, so a mismatch is a finding, not necessarily a bug.

## Step 8 (optional). Ordered dataset for the Phase 06 exact-match test

```bash
python -m data.generators.generate --preset small --late-rate 0 --replay-rate 0 --out data/raw/ordered
python -m data.generators.validate --data data/raw/ordered
python -m legacy_spark.retail_nightly_job --input data/raw/ordered --output output/legacy/ordered
```

Expected:
- Validation `PASS`, with replay and late_arrival counts both 0.
- The job completes.

Phase 06 compares this output with the correct marts.

## Step 9. Commit and push

First confirm Phase 01 is committed:

```bash
git log --oneline -5
```

If there is no `feat(data): implement reproducible retail data generator` commit, run the Phase 01 runbook Step 10 first. Otherwise its files would be mixed into this commit.

```bash
git status --short
```

Expected:
- New: `legacy_spark/`, `requirements-spark.txt`, `tests/unit/test_legacy_job.py`, `docs/diagrams/legacy-job.svg`.
- Modified: `.gitignore`, `README.md`, `docs/data_contracts.md`, `docs/diagrams/phase-plan.svg`, the Phase 01 handoff, and the Phase 02 documents.
- **No `output/`, `data/raw/` or `.venv*` entries.**

```bash
git add .gitignore legacy_spark requirements-spark.txt tests README.md docs phases
git status --short | grep -E 'output/|data/raw|\.venv|__pycache__|\.pytest_cache' || echo "no generated or local files staged"
git diff --cached | grep -nE 'dapi[0-9a-zA-Z]{16,}|DATABRICKS_TOKEN=[A-Za-z0-9]|https://[^[:space:]<]*databricks\.com'
git commit -m "feat(legacy): add legacy nightly PySpark job and baseline metrics"
git push
```

Expected:
- `no generated or local files staged`.
- The secret scan prints nothing.
- The push succeeds.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Java gateway process exited before sending its port number` / `JAVA_GATEWAY_EXITED` | No working Java, or `JAVA_HOME` points at the wrong place | Step 1; check `"$JAVA_HOME/bin/java" -version` |
| `UnsupportedClassVersionError` | Java older than 17 | Install Java 17 (Step 1) |
| Import or pickling errors from PySpark on Python 3.15 | PySpark does not support this Python yet | Step 2 fallback environment |
| `TypeError: reduce() of empty iterable` | `--input` has no `batch_NNN` folders | Point `--input` at a dataset folder, such as `data/raw/clean` |
| `AnalysisException ... cannot be resolved` naming a column | An input file lacks a column the job expects (L6) | Expected only for hand-edited files; regenerate the dataset |
| `ModuleNotFoundError: legacy_spark` | Not run from the repository root | `cd` to the root and use `python -m` |
| Run is slow the first time | JVM start and Spark initialisation | Normal; the second run is usually faster |

## Cleanup (destructive)

Deletes all legacy outputs under the git-ignored `output/` folder:

```bash
rm -rf output/legacy
```
