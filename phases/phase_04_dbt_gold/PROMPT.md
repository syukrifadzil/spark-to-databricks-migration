# Phase 04 — Dbt Gold

First read `GLOBAL_MASTER_INSTRUCTIONS.md` and follow every rule. Read the prior phase HANDOFF.md and existing source files where applicable using read-only file tools. Do not execute commands of any kind.

## Assignment
Create dbt Core Databricks project: sources for silver tables, staging models, gold marts (daily sales, customer lifetime value, product performance), YAML tests, custom business tests, docs and model lineage. Explain SQL and materialization choices, local credentials handling, SQL warehouse connection and manual dbt debug/run/test/docs commands. Avoid overlapping ownership with Lakeflow.

## Required deliverables
1. Create/edit the implementation files in canonical repository locations.
2. Write `phases/phase_04_dbt_gold/EXPLANATION.md` with detailed, beginner-accessible but senior-engineer-level explanation of each transformation, configuration, design decision, tradeoff and data flow.
3. Write `phases/phase_04_dbt_gold/MANUAL_RUNBOOK.md` containing numbered human-executable instructions, exact terminal commands, cwd, expected outputs, workspace UI clicks when needed, validation and troubleshooting. DO NOT execute any commands.
4. Write `phases/phase_04_dbt_gold/VALIDATION_CHECKLIST.md` with checkboxes for human-only execution, tests and acceptance criteria.
5. Write `phases/phase_04_dbt_gold/HANDOFF.md` with files changed, outstanding assumptions, risks, human outputs required, and the next phase's prerequisites.
6. Update the top-level README and relevant docs as necessary; avoid fabricated outcomes.
7. End your response with detailed explanations, exact git add/status/commit/push commands for me to run manually (do not execute), and a request for my execution results. Stop and wait for approval.

## Authorship and security
Write professional natural documentation with no AI traces, co-author lines, emojis, generated-by notices, or unsupported claims. Never commit credentials. Never execute, test, deploy, commit or push anything yourself.
