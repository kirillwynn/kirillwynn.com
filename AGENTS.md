# Codex project instructions

These instructions apply to the entire repository.

## Product context

`kirillwynn.com` is a personal publishing website. It is not a social-media
aggregator.

The private product specification lives locally in the author's Obsidian vault:

`~/.wisdom/wisdom/Projects/kirillwynn.com.md`

Read that note at the beginning of a product or implementation session when the
path is available. Do not copy the note into this repository. If it is not
available, continue from the repository documentation and mention the missing
product source in the handoff.

Repository sources of truth:

1. The user's current instructions.
2. The local Obsidian product specification, when available.
3. Accepted architecture decision records in `docs/decisions/`.
4. `docs/architecture.md`.
5. `docs/implementation-status.md`.
6. The current code and tests.

When these conflict, stop and reconcile the conflict explicitly. Do not silently
implement a different product.

## Target architecture

- Django 5.2 LTS and Wagtail 7.4 LTS own content and business data.
- PostgreSQL is the primary database.
- Next.js App Router with TypeScript owns the public UI.
- Wagtail Admin is the desktop authoring interface.
- django-allauth provides Google and GitHub OAuth.
- Django REST Framework exposes application APIs.
- S3-compatible object storage holds media.
- Nginx provides same-origin routing.
- Docker Compose runs the services on the existing server.

Read `docs/architecture.md` and
`docs/decisions/0001-django-wagtail-nextjs.md` before changing these
boundaries.

## Branch and scope

- `main` represents the currently deployed implementation and must remain
  releasable.
- The rebuild integration branch is `rewrite/wagtail-next`.
- Prefer one independently verifiable outcome per Codex session.
- Keep commits small and cohesive.
- Do not mix visual redesign with functional implementation unless the task
  explicitly requires it.
- Do not deploy or modify external production state without an explicit user
  request.

## Working rules

Before editing:

1. Read this file.
2. Read `docs/architecture.md`.
3. Read `docs/implementation-status.md`.
4. Read the relevant ADRs.
5. Inspect `git status` and preserve unrelated user changes.
6. Read the local Obsidian product note when available and relevant.

During implementation:

- Prefer vertical, end-to-end slices over disconnected scaffolding.
- Use Django migrations for all schema changes.
- Create the custom Django user model before the first new baseline migration.
- Treat the old Flask database and Alembic history as experimental; do not build
  compatibility migrations unless the user changes this decision.
- Keep public APIs REST-based. Do not introduce GraphQL.
- Keep all browser-facing routes on one origin through Nginx.
- Do not add Redis, Celery, Elasticsearch, or custom emoji to the first version
  without a new accepted ADR.
- Preserve database foreign keys. Do not use a generic relation for post and
  comment reactions.
- Store timestamps in UTC and localize only at presentation boundaries.
- Keep user-generated comments free of arbitrary HTML.
- Keep OAuth scopes minimal and do not retain provider tokens when identity is
  the only requirement.
- Never print, commit, or expose credentials. GitHub Environments remain the
  source of deployment secrets.

## Quality requirements

Every functional change must include proportionate verification.

Backend:

- Format and lint Python.
- Run relevant Django checks and tests.
- Add tests for model constraints, permissions, and API behavior.
- Test migrations from an empty database.

Frontend:

- Format and lint TypeScript.
- Run type checking and relevant tests.
- Cover interactive behavior with component or Playwright tests as appropriate.
- Preserve server rendering for content pages.

Cross-cutting:

- Verify mobile behavior at 375x812 when the change affects the public UI.
- Verify desktop behavior at 1440x900 when the change affects the public UI.
- Check keyboard access, visible focus, and non-hover interaction.
- Check CSRF, XSS, authorization, rate limiting, and open redirects where
  relevant.

Do not claim a check passed unless it was actually run. Record checks that could
not run and why.

## Session completion

At the end of every implementation session:

1. Review `git diff` and remove accidental changes.
2. Run the relevant verification commands.
3. Update `docs/implementation-status.md`.
4. Update the local Obsidian checklist when available, without copying the note
   into the repository.
5. Record remaining risks and the recommended next scope.
6. Report changed files and verification results to the user.

Follow `docs/development-workflow.md` for the detailed handoff format.
