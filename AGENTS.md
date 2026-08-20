# Repository Governance

## Delivery workflow

Work flows from Control Tower to one Builder, then to an independent Reviewer, and finally to explicit acceptance. Each Builder owns one worktree and one small milestone. A new milestone branch must start from a verified, current `origin/main` commit.

The legacy worktree, its Git staging state, all legacy code, and the existing staging environment are immutable product archaeology. Do not clean, reset, stash, switch, restore, stage, commit, copy, deploy to, or otherwise modify them.

The Builder implements only the authorized task contract. The Reviewer is read-only by default, independently verifies the evidence, and classifies findings as P0, P1, P2, or Accepted. An Accepted reviewer verdict still requires the Control Tower's explicit acceptance.

## Sources of truth

- [README.md](README.md) states the repository purpose and current status.
- [PLANS.md](PLANS.md) defines execution-plan and task-contract requirements.
- [docs/product.md](docs/product.md) defines product scope, roles, behavior, and non-goals.
- [docs/architecture.md](docs/architecture.md) defines hard constraints, logical boundaries, and the ADR backlog.
- [docs/roadmap.md](docs/roadmap.md) defines rolling-wave delivery order and gates.
- [docs/decisions/](docs/decisions/0000-template.md) contains append-only architecture decision records.
- [docs/handoffs/](docs/handoffs/README.md) defines Builder and Reviewer evidence handoffs.

If these documents conflict, stop and obtain a clarified task contract. Do not infer permission to expand scope.

## Repository policy

Until project tooling is adopted by an ADR and a milestone, only repository- and documentation-level checks are valid. Do not invent install, build, test, or run commands.

Do not push, deploy, open or modify a pull request, or mutate GitHub settings, Actions, rulesets, secrets, environments, infrastructure, providers, or production without separate explicit authorization. Keep secrets and real environment values outside Git.

Finance work is prohibited until a complete non-finance production release is working and accepted.

Accepted ADRs are historical records. Change an accepted decision with a new superseding ADR; never rewrite the old decision to change history.

## Definition of Done

A Builder milestone is complete only when:

- the authorized scope and public contracts are complete;
- all applicable checks are green and recorded with exact commands and results;
- the full diff has been inspected and contains no secrets or unrelated changes;
- exactly one authorized commit exists for the milestone;
- the milestone worktree is clean;
- a structured Builder handoff is ready for an independent Reviewer;
- the legacy worktree is unchanged; and
- no unauthorized external change occurred.
