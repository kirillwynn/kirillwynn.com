# Handoffs

Handoffs preserve exact evidence between a Builder, an independent Reviewer, and the Control Tower. They report completed work; they do not grant new scope.

## Builder handoff

Include:

- milestone and status;
- verified baseline commit and tree;
- worktree and branch;
- commit SHA, parent SHA, tree SHA, and subject;
- complete changed-file list using repository-relative Git paths;
- checks with exact commands and results, separated into pre-commit and post-commit evidence;
- inspected diff stat and concise per-file summary;
- external changes, explicitly stating `None` when applicable;
- deviations, residual risks, and open decisions;
- confirmation that the legacy worktree's branch, HEAD, staged, modified, and untracked state are unchanged; and
- the Reviewer's exact worktree and commit starting point.

Do not place a handoff that needs its own final commit SHA inside that same commit. Return it after the commit instead.

## Reviewer handoff

The Reviewer independently verifies the baseline, diff, and checks and classifies the result using the canonical [review severity definitions](../../AGENTS.md#review-severity). `Accepted` means there are no findings; any P0, P1, or P2 finding requires the verdict `Remediation required`.

The Reviewer is read-only by default and edits, stages, commits, pushes, deploys, or mutates external systems only under separate explicit authorization.
