# Phase 00 Handoff

## Status

Authored, not executed. No command, query or render in this phase has been run yet. Everything below under "Human outputs required" is blank until the maintainer fills it in.

## Files created or changed

| File | Change |
|---|---|
| `README.md` | Replaced the prompt-pack README with the project README |
| `.gitignore` | New |
| `.env.example` | New |
| `infra/sql/00_create_namespace.sql` | New |
| `docs/case_study.md` | New |
| `docs/architecture.md` | New |
| `docs/data_contracts.md` | New |
| `docs/platform_assumptions.md` | New |
| `docs/adr/README.md` | New |
| `docs/adr/0001-layer-ownership.md` to `docs/adr/0006-money-and-time-conventions.md` | New (six files) |
| `phases/phase_00_foundation/EXPLANATION.md` | Replaced placeholder |
| `phases/phase_00_foundation/MANUAL_RUNBOOK.md` | Replaced placeholder |
| `phases/phase_00_foundation/VALIDATION_CHECKLIST.md` | Replaced placeholder; original four items kept |
| `phases/phase_00_foundation/HANDOFF.md` | This file |
| `docs/diagrams/*.svg` (seven files) | New. Replaced all Mermaid diagrams after review: system context, as-is versus to-be, medallion ownership, incremental idempotency, orchestration, reconciliation, phase plan |
| `docs/data_contracts.md` | Refunds and partial payments modelled explicitly; `payment_type` added; amount rule changed to always positive |
| `docs/adr/*.md` | All six ADRs accepted on 2026-10-31 |

`GLOBAL_MASTER_INSTRUCTIONS.md` and the `PROMPT.md` files are unchanged.

## Outstanding assumptions

- All Free Edition items FE1 to FE15 in `docs/platform_assumptions.md`.
- Default catalog is named `workspace`.
- Lakeflow Python API is `pyspark.pipelines` with AUTO CDC available as `create_auto_cdc_flow`; to be confirmed before Phase 03.
- One pipeline can publish to two schemas (FE7); to be confirmed in Phase 03.
- The bundle product and CLI syntax referenced in the Phase 05 brief as "Declarative Automation Bundles"; to be confirmed before Phase 05.
- Timestamp format (UTC with `Z`) and identifier formats; to be finalised in Phase 01.

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Free Edition lacks a feature the design assumes | Phase 03 or 05 blocked | Fallback listed for every FE item |
| Free Edition quotas interrupt runs | Incomplete runs, delayed phases | Small data preset; spread runs |
| Lakeflow or bundle APIs renamed again | Code written against outdated syntax | Explicit verification step at the start of Phases 03 and 05 |
| SVG diagrams authored by hand without a render check | Overlapping text or misplaced arrows on GitHub | Runbook Step 9 checks every diagram; fix coordinates before Phase 01 |
| Secrets committed by accident | Credential exposure | `.gitignore`, `.env.example` placeholders, staged secret scan |
| CLI commands reach a non-project workspace | The maintainer's `~/.databrickscfg` has other profiles, and the default points at a different workspace | Always pass `-p <project profile>` or set `DATABRICKS_CONFIG_PROFILE`; Phase 05 bundle config pins the project host |

## Human outputs required

Fill in before requesting Phase 01.

- Tool versions (Runbook Step 2):
  - macOS:
  - Homebrew:
  - Git:
  - Python:
  - Java:
- `git check-ignore -v .env` output:
- Default catalog name (FE2): `workspace` (managed catalog), confirmed 2026-10-31.
- Namespace script result and verification query outputs (Step 7): script ran; `databricks schemas list workspace` shows `retail_bronze`, `retail_gold`, `retail_landing`, `retail_silver` with the expected comments; `databricks volumes list workspace retail_landing` shows the managed volume `raw`.
- Script re-run result: not yet reported.
- FE4 probe result (optional): not run.
- SQL warehouse name and size (no HTTP path needed here) (FE8): Serverless Starter Warehouse, 2X-Small.
- Databricks CLI version and `current-user me` result, redacted (optional): Databricks CLI v1.23.0 (Homebrew; an older shadowing copy was renamed). OAuth login succeeded; the project profile is the only profile and the default (`DATABRICKS_CONFIG_PROFILE` set in `~/.zshrc`). `current-user me` returned the maintainer's user, a member of `admins`. Unrelated profiles were removed from `~/.databrickscfg` after a backup.
- FE items observed as unavailable, and the fallback chosen: none observed unavailable. FE6 and FE9 confirmed only at API level; FE4, FE7, FE10, FE12, FE13, FE14 remain untested until the phases that need them.
- ADRs accepted, or comments: all six accepted (2026-10-31).
- Requested changes to Phase 00 documents: replace Mermaid with diagrams in a panelled card style (done, SVG); model refunds and partial payments (done in `docs/data_contracts.md`).
- Diagrams render on GitHub: not yet checked.
- Commit hash and repository URL after push: `ce7d125` (initial), `a3969b9` (CLI setup), https://github.com/syukrifadzil/spark-to-databricks-migration

## Phase 01 prerequisites

1. Phase 00 reviewed, committed and pushed.
2. Python version recorded; Phase 01 pins dependencies against it.
3. Conventions in `docs/data_contracts.md` agreed (they become the machine-readable contracts).
4. Refunds and partial payments: decided, modelled explicitly (`docs/data_contracts.md`, payments). Phase 01 fixes the type column name and the status values.
5. Explicit approval to start Phase 01.
