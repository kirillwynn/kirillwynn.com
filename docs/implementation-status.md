# Implementation status

Last updated: 2026-07-26

Integration branch: `rewrite/wagtail-next`

Overall state: Milestone 3 audit remediated; awaiting owner review

## Current repository state

- The `main` branch contains the deployed legacy Flask/React implementation.
- The legacy database and Alembic history are experimental.
- The new Django/Wagtail backend is isolated under `backend/django/`.
- The minimal Next.js Draft Mode and revalidation application is isolated under
  `frontend/next/`; the legacy Vite frontend remains unchanged.
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
- [x] Versioned anonymous live-only post list and slug detail API added.
- [x] One reusable public visibility policy excludes draft, unpublished,
  future, expired, and restricted pages.
- [x] Stable version 1.0 serialization covers metadata, deterministic tags,
  fixed image renditions, and all 13 StreamField blocks.
- [x] `wagtail-headless-preview` 0.9.0 integrated with Wagtail 7.4 redirect
  previews while retaining the backend-template fallback mode.
- [x] Opaque ten-minute credentials bind one immutable preview snapshot and
  resolve with private/no-store responses.
- [x] Wagtail publish, update, slug change, unpublish, and expiry events create
  signed revalidation records in a durable database outbox.
- [x] Retryable revalidation delivery and the
  `process_revalidation_outbox` management command added.
- [x] Minimal Next.js 16.2.11 / React 19.2.8 App Router scaffold added with
  strict TypeScript, Draft Mode entry/exit, diagnostic post preview, and HMAC
  revalidation.
- [x] API contract and ADR 0002 documented.
- [x] Milestone 3 audit remediated: explicit public-origin URLs, relative
  pagination, end-to-end Unicode slugs, aligned stable-ID/current/previous-slug
  cache tags, 32-byte revalidation secrets, environment-derived preview cookie
  security, and expanded Docker build-context exclusions.

## Milestone transition

Milestone 3 is complete. Its exit criteria pass with the local/test
filesystem-storage and SQLite configuration. S3, PostgreSQL-backed
verification, Nginx routing, and production scheduler invocation remain
deliberately separate infrastructure work.

### Next recommended session

Milestone 4: public Next.js shell, Feed, post renderer, and Bridge.

Scope:

1. Build the mobile-first Next.js layout and navigation without changing the
   content contract.
2. Implement the paginated Feed and post cards from `/api/v1/posts/`.
3. Replace the diagnostic page with renderers for all 13 typed body blocks.
4. Add public metadata, canonical, and Open Graph rendering.
5. Implement Bridge from configuration or Wagtail Site Settings.
6. Add component/Playwright coverage at 375x812 and 1440x900, including
   keyboard focus and non-hover behavior.

Out of scope for that session:

- public Feed/post visual implementation beyond the minimal preview endpoint;
- OAuth, comments, and reactions;
- search and tag filtering;
- S3 storage and production deployment;
- Nginx or production infrastructure changes;
- deletion of legacy reference files.

### Exit criteria

- Anonymous clients receive only currently public posts.
- Every content field and StreamField block has a stable versioned contract.
- Draft Mode renders one short-lived immutable snapshot without a browser URL
  token or public cache entry.
- Publish/unpublish cache events survive frontend failure and retry safely.
- Backend and minimal frontend verification pass.
- The status file and local Obsidian checklist are updated.

## Milestone queue

- [x] Milestone 1 — repository foundation and Django/Wagtail skeleton.
- [x] Milestone 2 — content pages, StreamField blocks, tags, media, revisions.
- [x] Milestone 3 — REST content API, preview, and cache revalidation.
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

- Exact Nginx exceptions for Next.js `/api/draft`, `/api/draft/disable`, and
  `/api/revalidate` are documented but deliberately not wired in this
  milestone.
- The Next.js duplicate-event registry is process-local. Duplicate invalidation
  remains safe across processes because tag/path invalidation is idempotent.
- Preview snapshot and delivered revalidation event retention are currently
  bounded only by opportunistic preview cleanup and database operations; a
  formal operations retention command belongs with worker infrastructure.
- Scheduled publishing is modelled and verified through Wagtail's
  `publish_scheduled_pages` command, but the production worker/cron invocation
  and `process_revalidation_outbox` schedule are deferred to the infrastructure
  milestone.
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
  locally. The Compose file parses as valid YAML. The Docker ignore rules were
  checked statically against the 138 MiB local `.next`, 407 MiB `node_modules`,
  and TypeScript build-info artifacts.
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

- `python3 -m uv lock --check` — passed; 46 packages resolved.
- `python3 -m uv run --frozen ruff format --check .` — passed (59 files).
- `python3 -m uv run --frozen ruff check .` — passed.
- `python3 -m uv run --frozen python manage.py check
  --settings=config.settings.test` — passed.
- `python3 -m uv run --frozen python manage.py makemigrations --check --dry-run
  --settings=config.settings.test` — passed; no changes detected.
- `python3 -m uv run --frozen pytest` — passed; 84 tests. Coverage includes an
  internal `Host: django:8000` with `PUBLIC_SITE_URL=https://kirillwynn.com`,
  canonical/rendition/lead/Open Graph/pagination/preview URL leakage checks,
  Unicode detail/canonical/internal-link and lifecycle revalidation, current
  and previous slug tags, absolute CDN URL preservation, short-secret rejection,
  and Secure/non-Secure preview cookie modes.
- Empty-file SQLite migration passed through all Django, Wagtail,
  `wagtail_headless_preview.0001_initial`, and
  `blog.0003_alter_revalidationevent_previous_slug_and_more` migrations.
- `migrate blog 0002` followed by `migrate blog 0003` passed on that clean
  SQLite database, verifying reverse/forward behavior for the new Unicode-slug
  migration.
- `python3 -m uv run --frozen python manage.py check --deploy` with production
  settings and safe non-secret verification values — passed; the
  Wagtail-required `X_FRAME_OPTIONS=SAMEORIGIN` warning is intentionally
  silenced.
- Production settings regression tests confirm that `PUBLIC_SITE_URL` is
  mandatory, normalized, and origin-only, and that production/runtime rejects
  `REVALIDATION_SECRET` values shorter than 32 UTF-8 bytes.
- Node.js 24.18.0 was selected through fnm. `npm ci` was not needed because
  neither dependencies nor lockfile changed.
- `npm run format:check`, `npm run lint`, and `npm run typecheck` — passed.
- `npm test` — passed; 37 Vitest tests in 6 files, including Unicode HMAC,
  parse/derive allowlists, unsafe slug rejection, single URL encoding,
  current/previous cache tags, and both preview cookie security modes.
- `npm run build` — passed with Next.js 16.2.11 and React/React DOM 19.2.8;
  `/api/draft`, `/api/draft/disable`, `/api/revalidate`, and `/posts/[slug]`
  are dynamic server routes. Built browser assets contain no revalidation
  secret name/value.
- Live local production-build Django/Next.js integration passed for the
  percent-encoded `/posts/привет-мир` route and server-rendered Unicode post.
  Signed Unicode revalidation returned `duplicate: false` and then
  `duplicate: true` for the identical event.
- Static Docker-context audit confirmed `.dockerignore` excludes `.next`,
  coverage, build info, package-manager caches/debug logs, and existing
  `node_modules`; no user caches were deleted.
- Docker, PostgreSQL server binaries, and `pg_isready` are not installed, so
  Docker and PostgreSQL-backed migration/search checks were not run. SQLite
  results are not represented as PostgreSQL verification.
