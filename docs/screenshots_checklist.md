# Screenshots Checklist

Screenshots make the portfolio easier to read, but each one can leak workspace details. Capture only what is listed here, redact as described, and commit only after the check at the end.

Save each image as `docs/screenshots/NN-name.png`. Reference it from the README only after it exists in the repository.

## Redaction rules

Every screenshot must show none of the following. Crop rather than blur where possible: a blur can sometimes be reversed.

| Item | Where it appears |
|---|---|
| Workspace host (`dbc-...cloud.databricks.com`) | Browser address bar; run and update URLs |
| Workspace id (`?o=` followed by digits) | Address bar |
| Email addresses | Browser tabs, account menu, "Run as" and owner fields, `userName` in `DESCRIBE HISTORY`, query history |
| Signed links | dbt `artifacts_link`; any URL containing `X-Databricks-Signature` |
| Other browser tabs and bookmarks | Browser chrome |
| Tokens, HTTP paths, warehouse ids | Connection details pages; never capture these pages |

The simplest approach is to capture the page content area only, with no browser chrome at all. On macOS, `Cmd+Shift+4` lets you drag a selection.

## Screenshots to capture

| No. | File | What to show | Where | Supports |
|---|---|---|---|---|
| 01 | `01-pipeline-graph.png` | Pipeline graph with the bronze, silver and quarantine datasets, and the last update completed | Jobs and Pipelines, the pipeline | Architecture, Phase 03 |
| 02 | `02-expectations.png` | Data quality tab of a silver dataset, with failed records counted | The pipeline, a silver table | Data quality |
| 03 | `03-job-run-success.png` | A `retail_nightly` run with `bronze_silver`, `gold` and `reconciliation` succeeded | Jobs and Pipelines, the job, Runs | Orchestration |
| 04 | `04-reconciliation-output.png` | The `reconciliation` task output, from `Reconciliation` to `RESULT: PASS` | The run, task `reconciliation` | AC10 |
| 05 | `05-reconciliation-failure.png` | A run with `dataset=clean` failing in `reconciliation` (R8) | The job's run history | Negative test |
| 06 | `06-audit-results.png` | `reconciliation/sql/01_latest_results.sql` results | SQL editor | AC10 |
| 07 | `07-gold-history.png` | `DESCRIBE HISTORY` of `mart_daily_sales` with the `RESTORE` row; crop off the `userName` column | SQL editor | R7 |
| 08 | `08-dbt-lineage.png` | dbt docs lineage graph for `mart_daily_sales` | `dbt docs serve`, locally | dbt gold |
| 09 | `09-catalog.png` | Catalog explorer showing the `retail_*` schemas | Catalog | Namespace |
| 10 | `10-ci-green.png` | A green `ci` workflow run with its three jobs | GitHub, Actions | AC9 |

Optional: the pipeline event log for a full refresh, or a few quarantine rows with the column that names the failed rules.

## Before committing

```bash
ls -la docs/screenshots/
```

Then open each file and check it against the redaction table. There is no automatic check for text inside images.
- Keep each file under about 500 KB.
- Large images make the repository slow to clone, and git keeps every version for good.
