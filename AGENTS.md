# Repository Governance

## Delivery workflow

Work flows from Control Tower to one Builder, then to an independent Reviewer, and finally to explicit acceptance. Each Builder owns one worktree and one small milestone. A new milestone branch must start from a verified, current `origin/main` commit.

The legacy worktree, its Git staging state, all legacy code, and the existing staging environment are immutable product archaeology. Do not clean, reset, stash, switch, restore, stage, commit, copy, deploy to, or otherwise modify them.

The Builder implements only the authorized task contract. The Reviewer is read-only by default, independently verifies the evidence, and classifies findings as P0, P1, P2, or Accepted. An Accepted reviewer verdict still requires the Control Tower's explicit acceptance.

## Review severity

- **P0 — blocking issue:** a security problem, secret exposure, invalid baseline or history, prohibited mutation, or another defect that prevents safe acceptance.
- **P1 — must fix before acceptance:** a task-contract violation, a missing required contract, or a material contradiction.
- **P2 — should fix:** a non-blocking issue with accuracy, clarity, or maintainability.
- **Accepted:** no findings.

If the Reviewer finds any P0, P1, or P2 issue, the verdict is `Remediation required`. Final acceptance belongs to the Control Tower.

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

## Documentation-only verification

Until accepted project tooling exists, the minimum reusable evidence set is:

- status, branch, and worktree topology;
- exact HEAD, parent, tree, and commit count relative to the baseline in the task contract;
- changed-file set and file modes read directly from Git;
- whitespace validation with `git diff --check` and inspection of the full diff;
- resolution of every relative Markdown target from the directory containing its source file;
- confirmation that the candidate contains no forbidden artifacts, executable or symlink modes, credentials, private-key or token values, or private filesystem paths; and
- confirmation that legacy-worktree metadata is unchanged.

Use safe read-only templates such as:

```sh
git --no-optional-locks status --short --branch
git worktree list --porcelain
git rev-parse HEAD HEAD^ 'HEAD^{tree}'
git rev-list --count BASELINE_SHA..HEAD
git diff --name-status BASELINE_SHA..HEAD
git diff --summary BASELINE_SHA..HEAD
git ls-tree -r --full-tree HEAD
git diff --check BASELINE_SHA..HEAD
git diff --no-ext-diff BASELINE_SHA..HEAD
```

Replace `BASELINE_SHA` with the exact SHA from the task contract. The task contract supplies any additional exact commands and expected outcomes. Do not add install, build, test, or run commands until accepted project tooling exists.

## Release Operator

The Release Operator is a separate role, not the Builder or Reviewer. This role participates only after explicit Control Tower authorization and only at agreed staging or production checkpoints. Authorization for one checkpoint grants no authority for any other external mutation. Builders and Reviewers do not receive deployment authority automatically.

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
