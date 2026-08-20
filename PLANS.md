# Execution Plans

Every milestone must begin with an authorized execution plan, also called a task contract. It is a bounded agreement, not permission for adjacent work.

## Required task-contract sections

1. **Milestone and goal.** Give the milestone identifier and one testable outcome.
2. **Verified baseline SHA.** Record the independently verified current `origin/main` commit and, when relevant, its tree.
3. **Context.** State the product and repository facts needed to perform the work.
4. **In scope.** Enumerate authorized changes.
5. **Out of scope.** Name nearby work that remains prohibited or deferred.
6. **Architecture constraints.** Separate accepted constraints from preferred directions and unresolved decisions.
7. **Expected files and public contracts.** List exact artifacts and observable obligations.
8. **Completion criteria.** Define the evidence required to call Builder work complete.
9. **Required checks.** Give exact commands or inspections and expected outcomes.
10. **Git policy.** Define worktree, branch, commit count, parent, staging, and history rules.
11. **Allowed external changes.** Default to none; enumerate any exception explicitly.
12. **Handoff format.** Define the evidence the Builder must return to the Reviewer.

## Execution record

Keep concise progress and evidence while executing the plan. Record assumptions and decisions before they affect the result. Record every deviation from the contract, including why it occurred and whether it needs remediation. An assumption never expands authorization.

## Builder handoff

The handoff must include milestone and status; verified baseline; worktree and branch; commit, parent, and tree SHAs; changed files; exact checks and results; inspected diff summary; external changes; deviations; residual risks; open decisions; legacy-worktree confirmation; and the Reviewer's exact starting point. Use the repository format in [docs/handoffs/README.md](docs/handoffs/README.md).

## Review and remediation

The independent Reviewer verifies the baseline, diff, and checks and classifies the result using the canonical [review severity definitions](AGENTS.md#review-severity). `Accepted` is permitted only when there are no findings; otherwise the verdict is `Remediation required`. The Reviewer edits nothing by default.

After a commit has been handed off, fixes are additive: create a separately authorized remediation milestone and commit. Never amend, rebase, or otherwise rewrite a handed-off commit.

## Default Git and external-change policy

Use one Builder, one worktree, one branch from verified current `origin/main`, and one small milestone. Stage only explicit authorized paths. Do not push, deploy, or mutate GitHub or external systems unless the task contract grants that exact action.
