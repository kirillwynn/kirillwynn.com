# Implementation status

Last updated: 2026-07-26

Integration branch: `rewrite/wagtail-next`

Overall state: Milestone 2 complete; awaiting owner review

## Current repository state

- The `main` branch contains the deployed legacy Flask/React implementation.
- The legacy database and Alembic history are experimental.
- The new Django/Wagtail backend is isolated under `backend/django/`.
- The Next.js application has not been scaffolded yet.
- Existing GitHub Actions, Nginx configuration, S3 utilities, social icons, and
  deployment secrets are reference material for the rebuild.
- The root `docker-compose.yml` remains the legacy deployment stack.
- `compose.dev.yml` is the new local Django/PostgreSQL stack and has no
  hard-coded container or network names.
- The private product specification remains in the local Obsidian vault and is
  not committed.

## Completed

- [x] Product functionality agreed with the owner.
- [x] Target stack selected.
- [x] Same-origin service boundaries selected.
- [x] Slack-style threads selected.
- [x] Unicode reactions selected instead of likes/dislikes.
- [x] Mobile authoring excluded from the first version.
- [x] Local Obsidian product specification expanded.
- [x] Rebuild integration branch created.
- [x] Repository-level Codex instructions added.
- [x] Initial architecture document added.
- [x] Initial architecture ADR added.
- [x] Cross-session development workflow added.
- [x] Legacy application and infrastructure inventoried without deletion.
- [x] Django 5.2.16 LTS and Wagtail 7.4.2 LTS scaffolded.
- [x] Django REST Framework and PostgreSQL environment configuration added.
- [x] Custom `users.User` created in the initial project migration.
- [x] Local, test, and production settings separated.
- [x] Wagtail Admin mounted at `/cms/`.
- [x] Django Admin mounted at `/django-admin/`.
- [x] Public health check mounted at `/api/health/`.
- [x] Python 3.12.13 and all Python dependencies locked.
- [x] Pytest, pytest-django, Ruff, system checks, and smoke tests added.
- [x] Local PostgreSQL/Django Compose stack documented.
- [x] Milestone 1 audit remediated: Django security patch, production Wagtail
  URL validation, Docker context exclusions, and configuration coverage added.
- [x] Singleton root-level `BlogIndexPage` and child-only `BlogPostPage` added.
- [x] Required excerpt, structured body, normalized tags, SEO, canonical, and
  Open Graph authoring fields added.
- [x] All 13 first-version StreamField block types added with explicit rich-text
  features and no raw HTML or embeds.
- [x] Wagtail Images alt/decorative validation and local rendition-backed
  backend preview added.
- [x] Draft revisions, preview, immediate publication, revision restoration,
  scheduled publication, and scheduled unpublication verified.
- [x] Blog migration, model constraints, page hierarchy, admin form, and block
  validation coverage added.

## Milestone transition

Milestone 2 is complete. Its exit criteria pass with the local/test
filesystem-storage and SQLite configuration. S3 and PostgreSQL-backed
verification remain deliberately separate infrastructure work.

### Next recommended session

Milestone 3: live content REST contract, signed headless preview, and cache
revalidation contract.

Scope:

1. Add paginated live-only post list and slug detail endpoints through DRF and
   Wagtail REST facilities.
2. Define stable API serialization for every StreamField block, tags, SEO/Open
   Graph fallbacks, and responsive Wagtail image rendition metadata.
3. Prove that drafts, future scheduled posts, expired posts, and non-requested
   revisions cannot enter the public API.
4. Implement a short-lived, tamper-resistant preview token bound to one Wagtail
   revision and the minimal Next.js Draft Mode endpoint needed to render it,
   without building the public UI.
5. Define signed publish/unpublish revalidation requests and test their
   authentication, idempotency, and failure behavior.
6. Add API contract, preview expiry/tampering, authorization, and cache
   revalidation tests.

Out of scope for that session:

- public Feed/post visual implementation beyond the minimal preview endpoint;
- OAuth providers;
- comments and reactions;
- S3 storage and production deployment;
- deletion of legacy reference files.

### Exit criteria

- Wagtail can author, revise, preview, publish, schedule, and roll back posts.
- Content models enforce the agreed page hierarchy and publication fields.
- Required StreamField blocks have stable backend definitions.
- Model and authoring behavior tests pass.
- The status file and local Obsidian checklist are updated.

## Milestone queue

- [x] Milestone 1 — repository foundation and Django/Wagtail skeleton.
- [x] Milestone 2 — content pages, StreamField blocks, tags, media, revisions.
- [ ] Milestone 3 — REST content API, preview, and cache revalidation.
- [ ] Milestone 4 — Next.js shell, Feed, post renderer, and Bridge.
- [ ] Milestone 5 — Google/GitHub OAuth and session integration.
- [ ] Milestone 6 — comments and Slack-style threads.
- [ ] Milestone 7 — post and comment reactions.
- [ ] Milestone 8 — PostgreSQL search and tag filtering.
- [ ] Milestone 9 — email subscriptions and durable outbox worker.
- [ ] Milestone 10 — isolated staging/production infrastructure.
- [ ] Milestone 11 — end-to-end hardening and functional launch.
- [ ] Milestone 12 — visual design and polish.

## Known risks

- Wagtail headless preview requires deliberate integration with Next.js Draft
  Mode.
- Scheduled publishing is modelled and verified through Wagtail's
  `publish_scheduled_pages` command, but the production worker/cron invocation
  is deferred to the infrastructure milestone.
- Media uses local filesystem storage in local/test. S3-compatible production
  storage, upload policy, and lifecycle configuration remain required.
- OAuth callbacks and credentials must be separate for staging and production.
- Current Docker Compose names collide if both environments run on one server.
- The current deployment workflow rebuilds production rather than promoting an
  already-tested staging image.
- The new backend currently coexists at `backend/django/` so the legacy Docker
  build remains intact. A later infrastructure milestone must promote the new
  backend to the final image layout deliberately.
- Docker build, Docker Compose config, and PostgreSQL-backed migrations remain
  unverified because Docker and PostgreSQL server binaries are not available
  locally. The Compose file parses as valid YAML, and the Docker build context
  and ignore rules were checked statically.
- Legacy migrations contain resets and multiple heads and should not be reused
  as the new baseline.
- Email DNS records and provider credentials do not exist in the current
  workflow.

## Decisions pending

No blocking product decisions are currently open.

Implementation-level choices should be recorded in a new ADR when they affect:

- service boundaries;
- persistence or migration strategy;
- authentication/session architecture;
- queue infrastructure;
- public API shape;
- deployment topology;
- a deliberately deferred dependency.

## Last verification

2026-07-26:

- `python3 -m uv lock --check` — passed; 45 packages resolved.
- Synced environment reports Python 3.12.13, Django 5.2.16, Wagtail 7.4.2,
  Django REST Framework 3.17.1, and Ruff 0.12.12.
- `python3 -m uv run --frozen ruff format --check .` — passed (38 files).
- `python3 -m uv run --frozen ruff check .` — passed.
- `python3 -m uv run --frozen python manage.py check
  --settings=config.settings.test` — passed.
- `python3 -m uv run --frozen python manage.py makemigrations --check --dry-run
  --settings=config.settings.test` — passed; no changes detected.
- `python3 -m uv run --frozen pytest` — passed; 36 tests, including Wagtail page
  hierarchy, every StreamField block, tags, draft preview and image renditions,
  revision restoration, immediate publish, and scheduled publish/unpublish.
- `python3 -m uv run --frozen python manage.py migrate --noinput
  --settings=config.settings.test` — passed from an empty in-memory SQLite
  database, including `blog.0001_initial`.
- An in-process `migrate` → `migrate blog zero` → `migrate blog` check passed,
  verifying reasonable forward/reverse behavior on SQLite.
- `python3 -m uv run --frozen python manage.py check --deploy` with production
  settings and safe non-secret verification values — passed; the
  Wagtail-required `X_FRAME_OPTIONS=SAMEORIGIN` warning is intentionally
  silenced.
- The production-settings regression test confirms that a missing
  `WAGTAIL_ADMIN_BASE_URL` raises `ImproperlyConfigured`.
- Docker, PostgreSQL server binaries, and `pg_isready` are not installed, so
  Docker and PostgreSQL-backed migration/search checks were not run. SQLite
  results are not represented as PostgreSQL verification.
