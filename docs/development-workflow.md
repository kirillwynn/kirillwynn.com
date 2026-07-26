# Development workflow

## Purpose

The rebuild is designed to span multiple focused Codex sessions without relying
on conversation history as the only source of context.

## Session sizing

Use one independently verifiable outcome per session.

Good scopes:

- scaffold Django/Wagtail with a custom user model;
- implement the content models and their tests;
- implement OAuth end to end;
- implement reactions end to end.

Scopes that are too broad:

- build the whole website;
- implement all backend functionality;
- finish staging and production.

Scopes that are too narrow:

- rename one internal variable;
- create one empty model without its behavior or tests;
- add one dependency without integrating it.

## Starting a session

1. Read `AGENTS.md`.
2. Read the local Obsidian product note when available:
   `~/.wisdom/wisdom/Projects/kirillwynn.com.md`.
3. Read `docs/architecture.md`.
4. Read `docs/implementation-status.md`.
5. Read relevant ADRs under `docs/decisions/`.
6. Inspect the current branch, status, recent commits, and relevant code.
7. Restate the session scope and exit criteria before editing.

Suggested prompt:

```text
Continue the kirillwynn.com rebuild.

Read AGENTS.md, the local Obsidian project note when available,
docs/architecture.md, docs/implementation-status.md, and relevant ADRs.

This session's scope:
<one concrete outcome>

Out of scope:
<explicit exclusions>

Implement the change, add proportionate tests, run verification, and update
docs/implementation-status.md plus the local Obsidian checklist.
```

## During a session

- Keep the task within the stated scope.
- Prefer a complete vertical slice when backend and frontend behavior are tightly
  coupled.
- Record a new architectural decision before silently changing an accepted
  boundary.
- Commit or checkpoint only coherent states.
- Preserve unrelated user changes.
- Do not use production as a test environment.

## Ending a session

1. Review the complete diff.
2. Run relevant formatting, linting, type checking, tests, and smoke checks.
3. Update `docs/implementation-status.md`:
   - completed work;
   - verification;
   - known risks;
   - next recommended scope.
4. Update the local Obsidian checklist when available.
5. Ensure the next session can resume from files and Git without reading the
   previous conversation.

Handoff format:

```text
Outcome
- What now works.

Changed
- Important files and migrations.

Verified
- Exact commands and results.

Not verified
- Checks that could not run and why.

Risks / follow-ups
- Known limitations or decisions needed.

Recommended next scope
- One independently verifiable outcome.
```

## Branch strategy

- `main` remains releasable.
- `rewrite/wagtail-next` is the rebuild integration branch.
- Use short-lived feature branches only when work is genuinely independent or
  parallel.
- Merge feature branches back into the rebuild branch after review and
  verification.
- Cut over to `main` only after the new stack passes staging acceptance.

## Commit strategy

Prefer commits that:

- express one intention;
- include tests with the behavior they verify;
- include migrations with their model changes;
- leave the repository runnable;
- avoid unrelated formatting churn.

Suggested prefixes:

- `docs:`
- `build:`
- `feat:`
- `fix:`
- `test:`
- `refactor:`
- `ops:`

## Definition of done for a session

A session is complete when:

- its stated outcome works;
- relevant tests pass;
- security and responsive implications were considered;
- documentation and status are current;
- no accidental files or secrets are present;
- the next scope is clear.
