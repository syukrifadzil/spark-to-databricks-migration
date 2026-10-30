# Phase 06 — Reconciliation Resilience

First read `GLOBAL_MASTER_INSTRUCTIONS.md` and follow every rule. Read the prior phase HANDOFF.md and existing source files where applicable using read-only file tools. Do not execute commands of any kind.

## Assignment
Implement legacy-versus-modern reconciliation scripts and SQL for row counts, totals, duplicates, missing keys, hash-based comparisons where appropriate; test plans for bad records, schema drift, late arrivals, reruns, recovery and rollback. Explain expected invariant vs acceptable differences. Include manual test matrix and evidence collection templates, no invented pass results.

## Required deliverables
1. Create/edit the implementation files in canonical repository locations.
2. Write `phases/phase_06_reconciliation_resilience/EXPLANATION.md` with detailed, beginner-accessible but senior-engineer-level explanation of each transformation, configuration, design decision, tradeoff and data flow.
3. Write `phases/phase_06_reconciliation_resilience/MANUAL_RUNBOOK.md` containing numbered human-executable instructions, exact terminal commands, cwd, expected outputs, workspace UI clicks when needed, validation and troubleshooting. DO NOT execute any commands.
4. Write `phases/phase_06_reconciliation_resilience/VALIDATION_CHECKLIST.md` with checkboxes for human-only execution, tests and acceptance criteria.
5. Write `phases/phase_06_reconciliation_resilience/HANDOFF.md` with files changed, outstanding assumptions, risks, human outputs required, and the next phase's prerequisites.
6. Update the top-level README and relevant docs as necessary; avoid fabricated outcomes.
7. End your response with detailed explanations, exact git add/status/commit/push commands for me to run manually (do not execute), and a request for my execution results. Stop and wait for approval.

## Authorship and security
Write professional natural documentation with no AI traces, co-author lines, emojis, generated-by notices, or unsupported claims. Never commit credentials. Never execute, test, deploy, commit or push anything yourself.
