# Phase 00 Manual Runbook: Foundation

All steps are executed by the maintainer. Nothing in this runbook has been run by the author of the files. Where an expected output is described rather than quoted, the exact text depends on your tool versions.

Repository root used below: `~/Desktop/databricks-prep/dbx-proj/spark-to-dbx`. Adjust if you move the folder. The GitHub repository name is `spark-to-databricks-migration`; the local folder name does not need to match.

## Prerequisites

- macOS with Terminal (zsh).
- A web browser and an email address for the Databricks Free Edition sign-up.
- A GitHub account.

## Step 1. Review the authored files

Working directory: repository root.

```bash
cd ~/Desktop/databricks-prep/dbx-proj/spark-to-dbx
ls -la
ls -R docs infra phases/phase_00_foundation
```

Expected: `README.md`, `GLOBAL_MASTER_INSTRUCTIONS.md`, `.gitignore`, `.env.example`, `docs/` (four documents and `adr/` with seven files), `infra/sql/00_create_namespace.sql`, and `phases/` with eight phase folders. `phase_00_foundation` holds `PROMPT.md`, `EXPLANATION.md`, `MANUAL_RUNBOOK.md`, `VALIDATION_CHECKLIST.md` and `HANDOFF.md`.

Read, in this order: `docs/case_study.md`, `docs/architecture.md`, `docs/data_contracts.md`, `docs/platform_assumptions.md`, `docs/adr/`. Note anything you disagree with; decisions are cheapest to change now.

## Step 2. Check local tools

Working directory: any.

```bash
sw_vers
brew --version
git --version
python3 --version
java -version
```

Expected:
- `sw_vers` prints your macOS version.
- `brew --version` prints a Homebrew version. If "command not found", install Homebrew from brew.sh, then open a new terminal.
- `git --version` prints a version. 2.28 or later is needed for `git init -b` in Step 5; otherwise use the fallback given there.
- `python3 --version` prints a 3.x version. Python is first needed in Phase 01. Record the version; Phase 01 pins dependencies against it.
- `java -version` may print "Unable to locate a Java Runtime". Java is first needed in Phase 02, so this is acceptable now. If you want to install it now: `brew install openjdk@17`, then follow the caveats Homebrew prints (they contain the exact symlink command for your machine). Afterwards, `/usr/libexec/java_home -v 17` should print a path.

Record all outputs for the HANDOFF (Step 10).

## Step 3. Create your local environment file

Working directory: repository root.

```bash
cp .env.example .env
chmod 600 .env
ls -l .env
```

Expected: `ls -l` shows `-rw-------` permissions. Leave placeholder values for now; they are filled in Phase 04. Never paste a token into `.env.example`.

## Step 4. Sign up for or open Databricks Free Edition

Browser:

1. Search for "Databricks Free Edition" and sign up from the databricks.com page, or log in if you already have an account.
2. Once the workspace opens, copy the URL from the address bar up to and including the host name, with nothing after it (`https://<workspace-host>`). This is your workspace host. You may put it in `.env` as `DATABRICKS_HOST`. Do not commit it.

## Step 5. Initialise git and confirm secrets are ignored

Working directory: repository root. The folder is not yet a git repository.

```bash
git init -b main
git status --short
git check-ignore -v .env
```

If `git init -b` is not supported by your git version:

```bash
git init
git symbolic-ref HEAD refs/heads/main
```

Expected:
- `git init` prints "Initialized empty Git repository in .../spark-to-dbx/.git/".
- `git status --short` lists untracked entries such as `?? .env.example`, `?? .gitignore`, `?? README.md`, `?? docs/`, `?? infra/`, `?? phases/`, `?? GLOBAL_MASTER_INSTRUCTIONS.md`. It must not list `.env`. If you have a `.claude/` or `.DS_Store` entry it must not appear either.
- `git check-ignore -v .env` prints a line like `.gitignore:3:.env	.env`. If it prints nothing, `.env` is not ignored: stop and check `.gitignore`.

## Step 6. Verify Free Edition capabilities in the UI

Browser, in the workspace. UI labels change between releases; if an item is not where described, use the workspace search box. Do not create pipelines, jobs or tokens in this step; only check that the option exists.

Open `docs/platform_assumptions.md` and fill in "Observed" and "Date" for each item you check:

| Check | Where to look | Records |
|---|---|---|
| FE1 | Compute page. Is creating an all-purpose cluster offered? | FE1 |
| FE2 | Catalog in the left sidebar. Which catalogs are listed? Is `workspace` present? | FE2 |
| FE5 | Catalog explorer, external data section. Can you create an external location? | FE5 |
| FE6 | Jobs and Pipelines. Is there an option to create an ETL pipeline? | FE6 |
| FE8 | SQL Warehouses (under Compute or SQL). Note the warehouse name, size and state. Open it, Connection details tab, note the HTTP path. | FE8 |
| FE9 | Jobs and Pipelines. Is there an option to create a job? | FE9 |
| FE11 | User settings, Developer section. Is "Access tokens" offered? | FE11 |
| FE13, FE15 | Any usage or quota information shown in the workspace or Free Edition documentation | FE13, FE15 |

You may put the HTTP path in `.env` as `DATABRICKS_HTTP_PATH`.

## Step 7. Create the namespace

Browser, SQL editor.

1. Open SQL Editor from the sidebar and attach the SQL warehouse found in Step 6 (the warehouse may take a short time to start).
2. If Step 6 showed that your catalog is not named `workspace`, edit the `USE CATALOG` line first, and set `RETAIL_CATALOG` in `.env` to match.
3. Paste the contents of `infra/sql/00_create_namespace.sql` and run all statements.
4. Run the two verification statements individually if the editor shows only the last result.

Expected:
- `SHOW SCHEMAS LIKE 'retail_*'` returns four rows: `retail_bronze`, `retail_gold`, `retail_landing`, `retail_silver`.
- `SHOW VOLUMES IN retail_landing` returns one row for `raw`.
- In Catalog explorer, `workspace > retail_landing > Volumes > raw` exists and is empty.

Re-running the script must succeed with no errors and no duplicates. Try it once to confirm.

Record the results against FE2 and FE3.

Optional probe for FE4 (whether you can create catalogs). This creates and immediately removes an empty catalog:

```sql
CREATE CATALOG IF NOT EXISTS retail_probe;
DROP CATALOG IF EXISTS retail_probe;
```

Record whether `CREATE CATALOG` succeeded or the error message. Either result is fine; the design does not depend on it.

## Step 8. Optional: install and authenticate the Databricks CLI

Needed from Phase 03; doing it now surfaces authentication problems early. Working directory: any.

```bash
brew tap databricks/tap
brew install databricks
databricks -v
databricks auth login --host https://<workspace-host>
databricks current-user me
```

Expected:
- `databricks -v` prints a version.
- `databricks auth login` opens a browser for OAuth consent and asks for a profile name (accept the default or type one). It writes a profile to `~/.databrickscfg`, which is outside the repository.
- `databricks current-user me` prints JSON including your `userName`.

Optional volume check:

```bash
databricks fs ls dbfs:/Volumes/workspace/retail_landing/raw
```

Expected: no output and no error, because the volume is empty. If the command syntax differs in your CLI version, check `databricks fs ls --help`.

Record against FE11.

## Step 9. Render the Mermaid diagrams

GitHub renders Mermaid in Markdown. Before pushing, you can preview with a Markdown viewer that supports Mermaid (VS Code with a Mermaid preview extension, or paste a block into the Mermaid live editor at mermaid.live). After pushing (Step 11), open each document on GitHub and confirm that every diagram renders. Diagrams are in `README.md`, `docs/case_study.md`, `docs/architecture.md` and `docs/data_contracts.md`.

## Step 10. Record results in the handoff

Fill in the "Human outputs required" section of `phases/phase_00_foundation/HANDOFF.md`, tick the items in `VALIDATION_CHECKLIST.md`, and change ADR statuses from Proposed to Accepted for those you agree with (both in the ADR file and in `docs/adr/README.md`).

## Step 11. Commit and push

Working directory: repository root. Requires Step 5 (`git init`); every git command below fails with "not a git repository" without it.

1. Stage explicitly named paths:

```bash
git add README.md GLOBAL_MASTER_INSTRUCTIONS.md .gitignore .env.example docs infra phases
git status --short
```

Expected: every line starts with `A `. `.env` must not appear.

2. Scan staged content for secrets:

```bash
git diff --cached --name-only
git diff --cached | grep -nE 'dapi[0-9a-zA-Z]{16,}|DATABRICKS_TOKEN=[A-Za-z0-9]|https://[^[:space:]<]*databricks\.com'
```

Expected: the first command lists only the files above. The second prints nothing (exit status 1). Any match must be removed from the file and re-staged before continuing. The pattern covers personal access tokens (which start with `dapi`), a filled-in token variable and a real workspace URL on a `databricks.com` domain. Placeholders such as `https://<workspace-host>` do not match. If your workspace host is on a different domain, also run `git diff --cached | grep -nF '<your actual host>'`.

3. Commit:

```bash
git commit -m "docs: add phase 00 foundation architecture and setup"
git log --oneline -1
```

Expected: one commit with that message.

4. Create an empty repository named `spark-to-databricks-migration` on GitHub (no README, no .gitignore, no license, to avoid a conflicting first commit). Then:

```bash
git remote add origin https://github.com/<your-github-username>/spark-to-databricks-migration.git
git push -u origin main
```

Expected: the push reports `main -> main` and sets upstream tracking. HTTPS pushes need a GitHub personal access token or a credential helper such as the GitHub CLI; SSH remotes (`git@github.com:<your-github-username>/spark-to-databricks-migration.git`) work if you have SSH keys configured.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `.env` appears in `git status` | `.gitignore` missing or renamed | Confirm `.gitignore` is in the repository root and contains `.env`; run `git rm --cached .env` if already staged |
| `git init -b` error "unknown switch" | Git older than 2.28 | Use the fallback in Step 5 |
| `USE CATALOG workspace` fails with catalog not found | Your default catalog has another name | Use the name shown in Catalog explorer; update the SQL file locally and `RETAIL_CATALOG` |
| `CREATE SCHEMA` permission denied | Your user cannot create schemas in that catalog (FE3 false) | Record it; fallback in ADR 0002 is a single schema with table prefixes. Report the error text before Phase 01 |
| `CREATE VOLUME` fails | Volumes unavailable or not permitted | Record the error; landing alternatives are evaluated before Phase 03 |
| SQL editor shows no warehouse | Warehouse stopped or not created | Start it from the SQL Warehouses page; record FE8 |
| `databricks auth login` browser loop or error | Wrong host URL or pop-up blocked | Use the exact host from the address bar, no path after the host |
| `databricks fs ls` "no such file" | Namespace not created or different catalog | Complete Step 7; adjust the catalog in the path |
| Mermaid diagram shows a syntax error on GitHub | Rendering issue in a label | Report the file and diagram; it will be fixed before Phase 01 |
| `git push` rejected (non-fast-forward) | GitHub repository was created with a README | Recreate it empty, or pull with `git pull --rebase origin main` and resolve |

## Teardown (destructive, only if you want to remove the namespace)

Removes all project objects in the catalog, including any data uploaded later. Do not run during normal work.

```sql
USE CATALOG workspace;
DROP SCHEMA IF EXISTS retail_gold CASCADE;
DROP SCHEMA IF EXISTS retail_silver CASCADE;
DROP SCHEMA IF EXISTS retail_bronze CASCADE;
DROP VOLUME IF EXISTS retail_landing.raw;
DROP SCHEMA IF EXISTS retail_landing CASCADE;
```

Once a Lakeflow pipeline exists (Phase 03), delete the pipeline before dropping its schemas.
