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
| Mermaid syntax not rendering | Documentation looks broken on GitHub | Runbook Step 9 checks every diagram |
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
- Namespace script result and verification query outputs (Step 7):
- Script re-run result:
- FE4 probe result (optional):
- SQL warehouse name and size (no HTTP path needed here) (FE8):
- Databricks CLI version and `current-user me` result, redacted (optional): Databricks CLI v1.23.0 (Homebrew; an older shadowing copy was renamed). OAuth login succeeded; the project profile is the only profile and the default (`DATABRICKS_CONFIG_PROFILE` set in `~/.zshrc`). `current-user me` returned the maintainer's user, a member of `admins`. Unrelated profiles were removed from `~/.databrickscfg` after a backup.
- FE items observed as unavailable, and the fallback chosen:
- ADRs accepted, or comments:
- Requested changes to Phase 00 documents:
- Commit hash and repository URL after push: `ce7d125`, https://github.com/syukrifadzil/spark-to-databricks-migration

## Phase 01 prerequisites

1. Phase 00 reviewed, committed and pushed.
2. Python version recorded; Phase 01 pins dependencies against it.
3. Conventions in `docs/data_contracts.md` agreed (they become the machine-readable contracts).
4. Decision on whether Phase 01 should model refunds and partial payments explicitly (affects the negative amount rule).
5. Explicit approval to start Phase 01.
