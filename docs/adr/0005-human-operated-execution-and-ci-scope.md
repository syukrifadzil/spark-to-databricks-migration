# 0005. Human-operated deployment; CI limited to static checks and unit tests

- Status: Accepted (2026-10-31)
- Date: 2026-10-30

## Context

The maintainer executes all commands, deployments and git operations manually, and documented results must come only from those runs. Workspace credentials in CI increase the blast radius of a leaked secret, and Free Edition may not support unattended deployment reliably.

## Decision

- GitHub Actions runs on pull requests and pushes: linting, formatting checks, unit tests that need no workspace, and dbt parsing with a placeholder profile if feasible.
- No workspace credentials are stored in GitHub in the baseline design.
- Bundle validation and deployment are run manually by the maintainer from a local terminal.
- If live deployment from CI is added later, it is a separate workflow, manually triggered, gated by a GitHub environment with required reviewers, using environment secrets.

## Alternatives considered

| Option | Benefits | Drawbacks |
|---|---|---|
| Full CI/CD with automatic deploy on merge | Production-like | Secrets in CI; deployments the maintainer did not observe; Free Edition support uncertain |
| No CI | Simplest | No automated guard on code quality; weaker portfolio |
| Static and unit CI only (chosen) | Safe, free, fast, no secrets | Integration issues are found only during manual runs |

## Consequences

- Integration testing against the workspace is a manual, documented step in each runbook.
- The production hardening table in `docs/case_study.md` describes what a gated deployment would add.

## Verification required

- Phase 05: confirm which checks can run without credentials (in particular dbt parsing).
