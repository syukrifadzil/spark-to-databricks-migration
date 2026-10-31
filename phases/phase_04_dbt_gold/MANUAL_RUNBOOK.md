# Phase 04 Manual Runbook: dbt Gold

All steps are run by the maintainer. None of these commands have been run by the author. Record the actual output of every step in `HANDOFF.md`; paste failures in full.

Terminal steps start from the repository root:

```bash
cd ~/Desktop/databricks-prep/dbx-proj/spark-to-dbx
```

SQL steps run in the workspace SQL Editor:
- Warehouse "Serverless Starter Warehouse".
- `pbcopy < <file>`, paste, then **Run all**.

## Step 0. Close Phases 02 and 03

Gold is built from silver, so silver must be shown correct first.

1. **Phase 02 Step 0** (in `phases/phase_03_lakeflow_bronze_silver/MANUAL_RUNBOOK.md`):
   - `python -m pytest -q` in `.venv`. Expected: `40 passed`, which now includes the two tests in `tests/unit/test_dbt_project.py`.
   - The anomalous legacy rerun. Expected: `5310.00 4472.00`.
   - The Phase 02 commit.
2. **Phase 03:** run `lakeflow/validation/01_layer_counts.sql`, `02_silver_vs_expected.sql` and `03_anomaly_checks.sql`, and compare them with Phase 03 runbook Step 11a. Then run its rerun and `batch_901` replay, and the Phase 03 commit (Step 13).

If a Phase 03 check fails, stop. Gold built on wrong silver would be wrong too.

## Step 1. Install dbt in its own environment

The environment must be created with `python3.12`, not `python`. Inside `.venv`, `python` is 3.15, and on 3.15 `pydantic-core` has no wheel and fails to build, because PyO3 0.26 supports Python up to 3.14 (observed 2026-10-31).

```bash
deactivate 2>/dev/null; rm -rf .venv-dbt
python3.12 --version || brew install python@3.12
python3.12 -m venv .venv-dbt
source .venv-dbt/bin/activate
python --version
python -m pip install --upgrade pip
python -m pip install -r requirements-dbt.txt
dbt --version
```

Expected:
- `python --version` prints `Python 3.12.x`. If it prints 3.15, stop: the environment was built from the wrong interpreter.
- `dbt --version` lists `Core` at 1.10.5 or later, and a `databricks` plugin.

`rm -rf .venv-dbt` deletes only this local environment. Paste the output; the versions get pinned in `requirements-dbt.txt` afterwards.

`.venv-dbt/` is git-ignored by the existing `.venv*/` pattern. Use this environment only for dbt. The tests and the legacy job stay in `.venv`.

## Step 2. Fill in the local `.env`

```bash
test -f .env || cp .env.example .env
databricks auth describe
databricks warehouses list
```

From the output:
- **`DATABRICKS_HOST`:** the `Host` line of `auth describe`, such as `https://dbc-xxxx.cloud.databricks.com`.
- **`DATABRICKS_HTTP_PATH`:** `/sql/1.0/warehouses/<ID>`, using the `ID` of "Serverless Starter Warehouse". The warehouse page shows the same path under **Connection details**.

Edit `.env`, for example with `open -e .env`, and set:

```
DATABRICKS_CONFIG_PROFILE=syukrifadzil
DATABRICKS_HOST=https://<your host>
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/<id>
DATABRICKS_TOKEN=
RETAIL_CATALOG=workspace
```

Leave `DATABRICKS_TOKEN` empty for OAuth. Do not paste `.env` contents into the conversation; the host and warehouse id are not secret, but there is no need to share them.

## Step 3. Create the local profile

```bash
cp dbt/profiles.example.yml dbt/profiles.yml
git check-ignore -v dbt/profiles.yml .env
```

Expected: two lines naming the `.gitignore` rules (`profiles.yml` and `.env`). If either file is not reported, stop: it would be committable.

## Step 4. Connect: `dbt debug`

```bash
cd dbt
set -a; source ../.env; set +a
dbt debug --profiles-dir .
```

Expected:
- A browser window opens for Databricks sign-in. Approve it.
- The output ends with `All checks passed!`.
- The connection test is `OK`, with catalog `workspace` and schema `retail_gold`.

Every later dbt command runs from `dbt/`, in a shell where `.env` has been sourced. Each new dbt command may open the sign-in window again.

**If OAuth fails** (an error during sign-in, or `Invalid auth`):
1. Create a personal access token in the workspace: your user menu > Settings > Developer > Access tokens > Generate new token. Give it a short lifetime, such as 7 days.
2. Put the token in `.env` as `DATABRICKS_TOKEN=...`, then `set -a; source ../.env; set +a` again.
3. Run `dbt debug --profiles-dir . --target token`, and add `--target token` to every later command.

Record which target worked; it fills FE11 in `docs/platform_assumptions.md`.

## Step 5. Build and test: `dbt build`

```bash
dbt build --profiles-dir .
```

`build` runs, in dependency order: the source tests, the five staging views, their tests, the three mart tables, and the mart and business tests.

Expected:
- 5 `view model` and 3 `table model` lines, each `OK`.
- Every error-severity test `PASS`.
- Exactly 4 `WARN` lines:
  - `relationships_orders_customer_id...`: 5
  - `relationships_order_items_product_id...`: 5
  - `relationships_payments_order_id...`: 5
  - `orders_paid_amount_matches`: 5
- A final summary of about `PASS=35 WARN=4 ERROR=0 SKIP=0 TOTAL=39`. The exact totals depend on how this dbt version counts nodes; the important part is `ERROR=0` and the four warnings.

Any `ERROR` stops dependent models; paste the full message. The compiled SQL is in `dbt/target/run/retail/`.

## Step 6. Inspect the warnings

In the SQL Editor, list the overpaid orders the business test found:

```sql
WITH items AS (SELECT order_id, SUM(line_total) AS total FROM workspace.retail_gold.stg_order_items GROUP BY order_id),
charges AS (SELECT order_id, SUM(amount) AS charged FROM workspace.retail_gold.stg_payments
            WHERE is_succeeded AND payment_type = 'charge' GROUP BY order_id)
SELECT o.order_id, o.status, i.total, c.charged
FROM workspace.retail_gold.stg_orders o JOIN items i USING (order_id) LEFT JOIN charges c USING (order_id)
WHERE o.is_sold AND COALESCE(c.charged, 0) <> i.total
ORDER BY o.order_id;
```

Expected: 5 rows, ORD-0000570, ORD-0000753, ORD-0001065, ORD-0003988 and ORD-0004038. Each has `charged` exactly 5.00 above `total`; these are the payment_mismatch orders in `_anomaly_manifest.json`.

## Step 7. Gold checks

Run `dbt/checks/04_gold_checks.sql` in the SQL Editor (`pbcopy < dbt/checks/04_gold_checks.sql` from the repository root).

Expected: 12 rows, all `ok`. In particular:
- **Row counts:** customer lifetime value has 530 rows and product performance 50; daily `orders_placed` sums to 5,310.
- **Net payments:** "daily net - lifetime net" is 50.00. Those are the five charges for the unknown order `ORD-X9999999`.

Then record the headline numbers:

```sql
SELECT 'daily' AS mart, COUNT(*) AS rows, SUM(orders_sold) AS orders_sold, SUM(gross_sales) AS gross,
       SUM(charges) AS charges, SUM(refunds) AS refunds, SUM(net_payments) AS net
FROM workspace.retail_gold.mart_daily_sales;
```

## Step 8. Ownership

```sql
SHOW TABLES IN workspace.retail_gold;
SHOW TABLES IN workspace.retail_silver;
```

Expected:
- `retail_gold`: exactly eight objects. These are `stg_customers`, `stg_products`, `stg_orders`, `stg_order_items` and `stg_payments` (views), and the three `mart_` tables.
- `retail_silver`: the ten pipeline tables (five entities, five quarantine) and nothing from dbt (AC8).

## Step 9. Docs and lineage

```bash
dbt docs generate --profiles-dir .
dbt docs serve --profiles-dir . --port 8080
```

A browser opens at `http://localhost:8080`:
- Open `mart_daily_sales` and check the column descriptions.
- Click the lineage button at the bottom right. With a model open, the graph shows only that model's lineage (`--select +mart_daily_sales+`). For `mart_daily_sales` expect three sources, `silver.orders`, `silver.order_items` and `silver.payments`, each feeding its staging view, and the three views feeding the mart. Clear the `--select` box and click **Update Graph** to see the whole project: five sources, five views, three marts.

`docs generate` may print agate `RuntimeWarning` lines such as `"table_owner" does not match the name of any column in this table`. They come from the adapter's catalog query and do not stop the run; what matters is the line `Catalog written to .../dbt/target/catalog.json`.

Stop the server with Ctrl+C. The docs are only local; `dbt/target/` is git-ignored.

Optional: in the workspace, Catalog > workspace > retail_gold > `mart_daily_sales` > Lineage. Record whether Unity Catalog shows silver and bronze upstream (ADR 0001 open item).

## Step 10. Rebuild idempotency

```bash
dbt build --profiles-dir .
```

Then run `dbt/checks/04_gold_checks.sql` and the headline query again. Expected:
- The same four warnings.
- All checks `ok`.
- Identical headline numbers.

## Step 11. Record the results

Paste into the conversation:
- `dbt --version`
- which target worked
- the `dbt build` summary and the warning lines
- the Step 6 to 8 query results
- whether the docs lineage looked as described

## Step 12. Commit and push

```bash
cd ~/Desktop/databricks-prep/dbx-proj/spark-to-dbx
git add dbt requirements-dbt.txt tests/unit/test_dbt_project.py README.md docs phases/phase_04_dbt_gold
git status --short
git status --short | grep -E 'profiles\.yml$|\.env$|dbt/target|dbt/logs|\.venv' || echo "no local or generated files staged"
git diff --cached | grep -nE 'dapi[0-9a-zA-Z]{16,}|DATABRICKS_TOKEN=[A-Za-z0-9]|https://[^[:space:]<]*databricks\.com'
git commit -m "feat(dbt): add gold marts, contract and business-rule tests"
git push
```

Expected:
- `dbt/profiles.example.yml` staged.
- `no local or generated files staged`. The grep matches `profiles.yml` only at the end of a name, so the example file does not count.
- The secret scan prints nothing.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `pip install` fails building a package | Missing wheel for this Python | Make sure `.venv-dbt` uses 3.12: `python --version` inside it |
| `Env var required but not provided: 'DATABRICKS_HOST'` | `.env` not sourced in this shell | `set -a; source ../.env; set +a` from `dbt/` |
| `Could not find profile named 'retail'` | `--profiles-dir .` missing or `profiles.yml` not created | Step 3; run from `dbt/` |
| OAuth window opens, then an error | OAuth for dbt not allowed in this workspace | Token target (Step 4) |
| `does not match dbt version required` | dbt older than 1.10.5 | `python -m pip install -U -r requirements-dbt.txt` |
| `TABLE_OR_VIEW_NOT_FOUND` for a silver table | Phase 03 not run, or a different catalog | Phase 03; check `RETAIL_CATALOG` |
| A function not found, such as `date_from_unix_date` | SQL warehouse version lacks it (section 6 of the explanation) | Paste the error |
| `PERMISSION_DENIED` creating in `retail_gold` | User lacks privileges on the schema | You own the schema (Phase 00); paste the message |
| `docs serve` fails with `[Errno 48] Address already in use` | Another process holds port 8080, such as an earlier `dbt docs serve` or a Docker container publishing 8080 (`com.docke...` in `lsof`) | `lsof -nP -iTCP:8080 -sTCP:LISTEN` to see it; stop it with Ctrl+C in its terminal, or serve on another port: `--port 8081` |
| Unexpected `ERROR` on a unique or not-null test | Silver or a mart breaks its grain | Paste the test name; run its SQL from `dbt/target/compiled/` in the SQL Editor |

## Cleanup (destructive, optional)

`dbt clean --profiles-dir .` removes `dbt/target/` and `dbt/dbt_packages/` locally. To remove the gold objects, drop them in the SQL Editor (`DROP VIEW` or `DROP TABLE` for each object in `retail_gold`). `dbt build` recreates them. Not needed between phases: Phase 06 reads them.
