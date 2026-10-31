# Phase 05 Manual Runbook: Orchestration and CI/CD

All steps are run by the maintainer. None of these commands have been run by the author. Record the actual output of every step in `HANDOFF.md`; paste failures in full.

**Working directory and environment for every terminal step:**

```bash
cd ~/Desktop/databricks-prep/dbx-proj/spark-to-dbx
source .venv/bin/activate
set -a; source .env; set +a
PIPELINE_ID=65b949fd-556c-47bd-ac1f-08855e9f7bd4
```

`.env` sets `DATABRICKS_CONFIG_PROFILE=syukrifadzil`, which every `databricks bundle` command uses to find the workspace. The pipeline id is the one created in Phase 03.

SQL steps run in the workspace SQL Editor, on "Serverless Starter Warehouse": `pbcopy < <file>`, paste, then **Run all**.

**Order matters.** Step 4 (bind) must come before Step 5 (deploy). If you deploy first, the bundle creates a second pipeline for the same tables (troubleshooting).

## Step 0. Close the Phase 04 follow-up

Run the `.user.yml` fix from the end of Phase 04 if you have not yet:

```bash
cat dbt/.user.yml
git rm --cached dbt/.user.yml
git add .gitignore phases/phase_04_dbt_gold
git commit -m "chore: stop tracking dbt .user.yml"
git push
git log --oneline -3
```

Expected:
- `cat` prints a single `id:` line.
- `git log` shows the new commit above `6f4ff73`.

If `git rm` says the path did not match, the fix is already done; `git log --oneline -3` is enough.

## Step 1. Check the CLI

```bash
databricks --version
databricks bundle deployment --help
databricks current-user me
```

Expected:
- A CLI version is printed. Paste it; it goes into the handoff.
- The `deployment` help lists `bind` and `unbind`. If `bind` is missing, the CLI is too old: `brew upgrade databricks`.
- Your user record, from the `syukrifadzil` profile.

## Step 2. Local unit tests

```bash
python -m pytest -q
```

Expected: `41 passed`. That is the 40 from Phase 04 plus `tests/unit/test_bundle.py`. If `test_job_installs_the_pinned_dbt_versions` fails, the dbt versions in `databricks.yml` and `requirements-dbt.txt` differ.

## Step 3. Dry validation

```bash
databricks bundle validate
```

Expected output, with your own values:

```
Name: spark_to_databricks_migration
Target: dev
Workspace:
  User: <your user>
  Path: /Workspace/Users/<your user>/.bundle/spark_to_databricks_migration/dev

Validation OK!
```

Warnings about unknown properties must be pasted; they mean a field name is wrong for this CLI version.

Then print the settings as the bundle resolved them:

```bash
databricks bundle validate -o json | python -c '
import json, sys
r = json.load(sys.stdin)["resources"]
p = r["pipelines"]["retail_bronze_silver"]
print(p["name"])
print(p["libraries"])
print(json.dumps(p["configuration"], indent=1))
t = r["jobs"]["retail_nightly"]["tasks"]
print([x["task_key"] for x in t])
print(t[1]["dbt_task"])'
```

Expected:
- **Name:** `[dev <your short name>] retail_bronze_silver`.
- **Libraries:** one glob, `/Workspace/Users/<your user>/.bundle/spark_to_databricks_migration/dev/files/lakeflow/transformations/**`. This checks V3.
- **`retail.code_root` and `retail.contract_path`:** under the same `.../dev/files/` folder (V4).
- **`retail.landing_path`:** `/Volumes/workspace/retail_landing/raw/retail`.
- **Tasks:** `['bronze_silver', 'gold']`.
- **`dbt_task`:** `warehouse_id` resolved to an id rather than `${var.warehouse_id}`, `catalog` is `workspace`, `schema` is `retail_gold`, and `project_directory` points at `dbt`.

Nothing has changed in the workspace yet. Stop here and paste the output if any value is different.

## Step 4. Adopt the Phase 03 pipeline

### 4a. Record the state before

Make sure no update is running:

```bash
databricks pipelines list-updates $PIPELINE_ID --max-results 1 | grep '"state"'
```

Expected: `COMPLETED`, `FAILED` or `CANCELED`. If it shows `RUNNING` or another active state, wait (Phase 03 runbook, "Waiting for an update").

In the SQL Editor, run `lakeflow/validation/01_layer_counts.sql` and keep the result. Step 7 compares against it.

### 4b. Bind

```bash
databricks bundle deployment bind retail_bronze_silver $PIPELINE_ID
```

The command first prints the changes the next deploy will make:
- the library glob, `retail.code_root` and `retail.contract_path`, moving to `.../dev/files/`
- the `[dev <you>]` name prefix and `dev` tag
- `deployment`
- `edition: null -> "ADVANCED"`

Answer `y` to the confirmation. Expected: `Successfully bound pipeline with an id '65b949fd-556c-47bd-ac1f-08855e9f7bd4'`. The pipeline itself does not change until Step 5.

## Step 5. Deploy

```bash
databricks bundle deploy --fail-on-active-runs
databricks bundle summary
```

Expected:
- **`deploy`, first time:**
  - `Updated pipelines.retail_bronze_silver`
  - `Created jobs.retail_nightly`
  - a `Files: <n> uploaded` line
  - `Resources: 1 created, 1 changed, 0 deleted`
  - A `deleted` count above 0 means something would be removed; stop and paste the output.
- **`summary`:** lists the job `[dev <you>] retail_nightly` and the pipeline `[dev <you>] retail_bronze_silver`, each with a workspace URL. The pipeline URL contains `65b949fd-556c-47bd-ac1f-08855e9f7bd4`. A different id means the bind did not take; see troubleshooting.

Check that the pipeline now reads its code from the bundle:

```bash
databricks pipelines get $PIPELINE_ID | python -c '
import json, sys
s = json.load(sys.stdin)["spec"]
print(s["name"]); print(s["development"]); print(s["libraries"]); print(s["configuration"]["retail.code_root"])'
```

Expected:
- the prefixed name
- `True`
- the glob and the code root under `.../.bundle/spark_to_databricks_migration/dev/files/`

Check what was uploaded. The folder is the `Path:` line from Step 3 plus `/files`, in the workspace (not the landing volume):

```bash
BUNDLE_FILES="/Workspace/Users/<your user>/.bundle/spark_to_databricks_migration/dev/files"
databricks workspace list "$BUNDLE_FILES"
databricks workspace list "$BUNDLE_FILES/data"
databricks workspace list "$BUNDLE_FILES/dbt"
```

Expected:
- **Top level:** `lakeflow`, `dbt`, `data`, `docs` and the other committed folders. No `.env`, no `output`, no `.venv-dbt`.
- **`data`:** `contracts`, `generators`, `samples`, with no `raw`.
- **`dbt`:** no `profiles.yml`, `target` or `logs`.

This is V14. If a git-ignored file was uploaded, stop and paste the listing.

## Step 6. Run the job

```bash
databricks bundle run retail_nightly
```

The command prints a run URL and waits. Expected:
- `bronze_silver` succeeds. It is an incremental update with no new files.
- `gold` succeeds.
- The command exits without an error.

The first run may take several minutes: the serverless environment installs dbt, and the warehouse may need to start. Record the total time shown on the run page. The first run on 2026-11-01 took about three and a half minutes.

The command ends with `TERMINATED SUCCESS` and a `Dbt Task Output` block that holds only an `artifacts_link`. That link is a signed, time-limited download URL for the dbt output: do not paste it anywhere public or into any file.

Open the run URL, then the `gold` task. Its output is the dbt log. Expected: the same result as Phase 04, which is `ERROR=0` and four `WARN` lines (three relationships tests and `orders_paid_amount_matches`).

If `gold` fails, paste the first error in its output and go to the troubleshooting table. The fallbacks are in EXPLANATION section 7.

## Step 7. Check nothing changed

The job ran with no new landing files, so the data must be unchanged:

1. Run `lakeflow/validation/01_layer_counts.sql` again. Expected: identical to Step 4a, including the fingerprints. This is AC5 again, now through the bundle-deployed code path.
2. Run `dbt/checks/04_gold_checks.sql`. Expected: 12 rows, all `ok`.
3. Run the Phase 04 headline query (Phase 04 runbook Step 7). Expected: the same numbers as in Phase 04.

## Step 8. Free Edition findings

Record, for `docs/platform_assumptions.md`:
- **FE9:** whether the job ran, and any quota message.
- **FE10:** whether the dbt task ran.
- **FE12:** whether `bundle deploy` worked.
- **FE14:** whether the serverless environment installed dbt from PyPI.

## Step 9. Optional: remove the Phase 03 upload

Once Step 6 has succeeded, the pipeline no longer reads `/Workspace/Shared/spark-to-databricks-migration`. Removing it is optional, and it is destructive:

```bash
databricks workspace list /Workspace/Shared/spark-to-databricks-migration
databricks workspace delete --recursive /Workspace/Shared/spark-to-databricks-migration
```

Only do this after Step 5 shows the pipeline's paths under `.bundle`. Keeping it costs nothing. Note that the Phase 03 runbook uploads it again if ever replayed.

## Step 10. Commit and push

```bash
git add databricks.yml .github tests/unit/test_bundle.py lakeflow/transformations/retail_pipeline.py \
        docs README.md phases/phase_05_orchestration_cicd
git status --short
git status --short | grep -E 'profiles\.yml$|\.env$|\.user\.yml$|\.databricks/|dbt/target|dbt/logs|\.venv' || echo "no local or generated files staged"
git diff --cached | grep -nE 'dapi[0-9a-zA-Z]{16,}|DATABRICKS_TOKEN=[A-Za-z0-9]|https://[^[:space:]<]*databricks\.com' | grep -vE 'https://docs\.databricks\.com|dbc-xxxx'
git commit -m "feat(orchestration): add bundle, job and CI workflow"
git push
```

Expected:
- **Staged:** `databricks.yml`, `.github/workflows/ci.yml`, the new test, and the docs and phase files.
- **Staged-files check:** prints `no local or generated files staged`. `.databricks/` is the bundle's local state folder and is git-ignored.
- **Secret scan:** prints nothing. If it prints a line, do not commit; paste the line.

## Step 11. Check CI

On GitHub, open the repository, then **Actions** > **ci** > the run for your push.

Expected: three green jobs.
- **`unit-tests`:** the `pytest` step ends with `41 passed` and has no `SKIPPED` lines. A skipped Spark test means Java was not found.
- **`dbt-parse`:** ends without an error. That confirms V16: parsing works with a placeholder profile.
- **`secret-scan`:** passes.

Paste the run URL and, for any red job, its failing step log.

**Optional, for AC9 ("on pull requests"):** open a draft pull request from a throwaway branch and check that the same three jobs run on it:

```bash
git switch -c ci-check
git commit --allow-empty -m "chore: check CI on a pull request"
git push -u origin ci-check
```

GitHub prints a link to open the pull request. After the checks finish:
1. Close the pull request without merging.
2. Run `git switch main`, `git branch -D ci-check` and `git push origin --delete ci-check`.

## Step 12. Record the results

Paste into the conversation:
- the Databricks CLI version
- the Step 3 output
- the Step 5 `summary` and pipeline settings
- the Step 6 run result and the dbt summary line from the `gold` task
- the Step 7 comparison
- the Step 8 findings
- the CI run URL and the job results

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `validate`: lookup finds no warehouse | Warehouse has another name | Add `--var warehouse_id=<id>` to every bundle command (id from `databricks warehouses list`) |
| `validate` or `deploy`: authentication error | `.env` not sourced, or OAuth session expired | `set -a; source .env; set +a`, then `databricks auth login --profile syukrifadzil` |
| `deploy`: the pipeline would be recreated, refused by `prevent_destroy` | A setting that forces a new pipeline changed, or the bind is missing | Do not override. Paste the message |
| `summary` shows a pipeline id other than `65b949fd-...` | Deploy ran before the bind | Do not run the new pipeline. Check `databricks pipelines get <new id>` names `[dev ...] retail_bronze_silver` and has no updates. Remove it with `databricks bundle deployment unbind retail_bronze_silver` then `databricks pipelines delete <new id>`. Then repeat Steps 4b and 5 |
| `deploy` refused: active run | An update is running | Wait, then deploy again |
| `bronze_silver` fails: contract file not found, or `ModuleNotFoundError: retail_rules` | Synced path differs from what the configuration expects | Paste the update error and the Step 5 pipeline settings |
| `gold` fails: `Could not find profile named 'retail'` | The supplied profile has another name (V9) | Fallback F2 in EXPLANATION section 7 |
| `gold` fails installing packages | No PyPI access, or environment version 4 unavailable | Set `environment_version: "3"`, deploy, run again. Otherwise fallback F3 |
| `gold` fails: `TABLE_OR_VIEW_NOT_FOUND` | Catalog or schema differ | Paste the dbt error |
| CI: `Unable to resolve action` | Action major version not available | Lower it in `ci.yml` (for example `@v6`), push again |
| CI `dbt-parse`: connection error | dbt tried to connect (V16 false) | Remove the `dbt-parse` job and record the finding |

## Rollback

To return to the Phase 03 setup:
1. `databricks bundle deployment unbind retail_bronze_silver`. The pipeline stays, and so do its tables.
2. If Step 9 removed `/Workspace/Shared/spark-to-databricks-migration`, repeat the Phase 03 runbook's code upload first. Then restore its Phase 03 settings: `databricks pipelines update $PIPELINE_ID --json @lakeflow/pipeline.json`.
   - This command is not verified. If it is rejected, set the library path and the two `retail.*` paths back to `/Workspace/Shared/...` in the pipeline's settings in the UI.
   - The Phase 03 code must still be in `/Workspace/Shared`, so skip Step 9 if you may roll back.
3. Delete the job in the UI: Jobs and Pipelines > `[dev ...] retail_nightly` > Delete.

Never run `databricks bundle destroy` while the pipeline is bound. `prevent_destroy` should refuse it, but the tables are not worth the test.
