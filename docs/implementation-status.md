# Implementation status

Last updated: 2026-07-27

Integration branch: `rewrite/wagtail-next`

Overall state: Milestone 9 production-ready email subscription application
boundary implemented and locally verified; live Resend/DNS, PostgreSQL-only
locking, scheduled worker infrastructure, and live-browser checks remain
external or unavailable

## Current repository state

- The `main` branch contains the deployed legacy Flask/React implementation.
- The legacy database and Alembic history are experimental.
- The new Django/Wagtail backend is isolated under `backend/django/`.
- The public Next.js application is isolated under `frontend/next/`; the legacy
  Vite frontend remains unchanged.
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
- [x] Tailwind CSS 4.3.3 and its PostCSS integration added without upgrading
  Next.js 16.2.11 or React 19.2.8.
- [x] Mobile-first public shell added with system fonts, Feed/Bridge
  navigation, an honestly disabled Login control, footer, skip link, visible
  focus, and reduced-motion handling.
- [x] Typed public post-list client added with positive-page validation, the
  `posts` list cache tag, granular detail cache tags, Unicode route boundaries,
  and distinct 404/upstream handling.
- [x] Server-rendered Feed added with semantic post cards, lead renditions,
  tags as metadata, accessible pagination, and empty/loading/error/not-found
  states.
- [x] Public and Draft Mode post pages now share one exhaustive renderer for all
  13 StreamField blocks; diagnostic JSON and internal identifiers were removed.
- [x] Fixed responsive image renditions, decorative/contextual alt behavior,
  accessible table headers, read-only checklists, safe links, and server-side
  code highlighting with an unknown-language plain-text fallback added.
- [x] Per-post SEO, canonical, Open Graph article metadata, timestamps, tags,
  images, and Draft Mode noindex metadata added.
- [x] Bridge added with exactly eight approved external links, the reused
  legacy SVG assets, and Yandex/Deeplay team labels.
- [x] Frontend coverage expanded from 37 to 65 Vitest tests, including every
  block type, Feed/client/cache behavior, metadata, preview, Bridge, disabled
  Login, and browser-bundle security boundaries.
- [x] django-allauth 65.18.0 socialaccount integration added for Google and
  GitHub with settings-only `APPS`, minimal scopes, Google PKCE/online access,
  POST-only initiation, provider timeouts, and no retained tokens.
- [x] Public local allauth password/signup flows disabled with
  `SOCIALACCOUNT_ONLY`; Django `ModelBackend` remains available for Wagtail and
  Django administrator password login.
- [x] Verified provider emails safely match and connect existing users,
  unverified emails are rejected, repeated login is idempotent, explicit
  second-provider connection is available, and provider identities cannot be
  reassigned between users.
- [x] Django database sessions, hardened production `__Host-` cookies, masked
  CSRF delivery, one-proxy allauth client-IP trust, login session rotation, and
  explicit production trusted-origin/credential requirements added.
- [x] `GET /api/me/` and CSRF-protected `POST /api/auth/logout/` added with
  private/no-store responses and minimal current-user/provider data.
- [x] Backend-only canonical return-to validation requires exactly one leading
  slash before and after strict decoding, then allowlists `/`, `/bridge`,
  `/account`, and Unicode `/posts/<slug>` while rejecting network-path,
  malformed/double-encoded, backslash, control-character, fragment, extra-path,
  and internal-service targets.
- [x] Google and GitHub OAuth initiation/state/callback regression coverage
  proves malicious `next` values are discarded and callbacks fall back to `/`.
- [x] Production OAuth credential validation trims values before fail-fast
  checks, rejects missing/empty/whitespace-only values, guarantees both provider
  `APPS`, and requires a finite positive provider timeout.
- [x] Fixed Next.js same-origin rewrites added only for `/accounts/*`,
  `/api/me/`, and `/api/auth/logout/`, preserving the existing frontend API
  routes.
- [x] `/login`, `/account`, provider POST forms, connected-provider state,
  unavailable/error states, responsive header auth state, accessible user menu,
  expired-session recovery, and CSRF logout added.
- [x] `promote_site_owner` safely and idempotently promotes only an existing
  verified Google/GitHub user selected through `SITE_OWNER_EMAIL`.
- [x] OAuth setup, callback URLs, GitHub Environment names, session/API
  contracts, and external application tasks documented without creating or
  modifying provider applications or deployment secrets.
- [x] Concrete `Comment` model added with protected post/user identities,
  direct top-level roots, derived reply mentions, soft deletion, moderation
  state, UTC timestamps, database constraints, and stable indexes.
- [x] Anonymous comment/thread reads and session/CSRF-protected create, reply,
  edit, and delete APIs added under exact versioned routes.
- [x] The canonical public post visibility service gates every discussion
  route; draft, unpublished, future, expired, and restricted posts remain 404.
- [x] Cursor pagination provides newest-first roots, oldest-first one-level
  replies, relative links, and annotated reply counts/activity without N+1.
- [x] Plain-text normalization, 5000-code-point limit, control-character
  rejection, escaped React text rendering, hidden/deleted tombstones, and
  no-op edit behavior added.
- [x] Django Admin hide/unhide and user ban/unban actions added with ordinary
  hard comment deletion disabled.
- [x] Database-backed fixed-window per-user mutation limits added with one row
  per `(user, scope)`, row locking, race-safe unique creation, `429`, and
  `Retry-After`.
- [x] Public post comments UI added with anonymous, authenticated, banned,
  loading, empty, retry, validation, edit/delete, and cursor load-more states.
- [x] Slack-style desktop drawer and mobile full-screen thread layer added with
  pinned root/composer, one-level replies, mention labels, query-string
  navigation, Escape/focus handling, safe-area padding, and scroll containment.
- [x] Comment and reply drafts survive OAuth/session expiry through bounded,
  TTL-scoped `sessionStorage` namespaces and are never submitted automatically.
- [x] Milestone 6 frontend remediation gives anonymous readers real root/reply
  textareas, saves every change under `pending-auth`, migrates the newest draft
  to the authenticated user after OAuth, and clears it only on submit/discard.
- [x] Root, reply, edit, paste, counter, and draft paths share a 5000 Unicode
  code-point limit without UTF-16 `maxlength` truncation or split surrogate
  pairs.
- [x] Stable-ID reconciliation deduplicates optimistic and cursor-loaded
  comments, refreshes server objects, preserves root/reply ordering, and
  replaces thread activity summaries without double increments.
- [x] Exact comment rewrites added without a generic `/api/:path*` proxy or
  collision with auth, Draft Mode, or revalidation.
- [x] Concrete protected `PostReaction` and `CommentReaction` tables added with
  canonical emoji keys, uniqueness constraints, and aggregation/participant
  indexes.
- [x] NFC normalization and `emoji` 2.15.0 RGI validation support ZWJ,
  modifiers, flags, keycaps, gender/variation sequences, while rejecting text,
  multiple emoji, controls/bidi, lone components, and malformed input.
- [x] Anonymous aggregate reads, session/CSRF-protected transactional toggles,
  exact private participant endpoints, stable relative cursors, and minimal
  participant identity added.
- [x] Target-row PostgreSQL locking, unique-constraint fallback, and a
  database-backed 60-per-60-second reaction toggle limiter added.
- [x] Comment/thread contracts embed reaction groups and viewer state through
  bounded page-level queries; tombstones suppress UI, aggregates, participants,
  and new toggles while retaining rows.
- [x] Wagtail `ReactionSettings` exposes exactly three validated distinct quick
  reactions through a minimal public config endpoint.
- [x] Post, top-level comment, and reply pills added with `aria-pressed`,
  touch-sized quick/picker/participant controls, optimistic rollback, a
  synchronous double-click guard, and authoritative response replacement.
- [x] The locally bundled Unicode 15 Emoji Mart dataset lazy-loads only when the
  searchable keyboard picker opens; recent emoji are bounded and contain no
  identity/session data.
- [x] OAuth reaction intent is TTL-scoped in `sessionStorage` by Unicode slug,
  target type/ID, and emoji, then restored as an explicit confirmation instead
  of an automatically replayed toggle.
- [x] Exact reaction rewrites preserve auth, comments, Draft Mode, preview, and
  revalidation boundaries; Draft Mode renders no reaction UI.
- [x] ADR 0003 and the complete reaction API/security/concurrency contract are
  documented.
- [x] Milestone 7 remediation rejects every surrogate before UTF-8 encoding,
  returns stable JSON 400 responses, and applies the same safe validator to
  reaction model and Wagtail setting saves.
- [x] Compact deterministic frontend sequence validation rejects malformed
  stored ZWJ/flag/variation forms while preserving the full Emoji Mart dataset
  behind its lazy picker boundary.
- [x] Pending reaction intent storage keeps one newest `createdAt` entry per
  Unicode slug/target, clears the whole target on confirm/discard, and isolates
  other targets.
- [x] Participant requests use abort/request identities, current-group cursor
  checks, ID deduplication, target/close/unmount invalidation, Escape focus
  restoration, and mouse/fine-pointer-only hover.
- [x] Comment reaction reconciliation now uses mutation revisions with
  transient optimistic markers; matching authoritative/rollback results settle
  them, later server aggregates refresh normally, and tombstones always win.
- [x] A shared per-target frontend coordinator now gives duplicate list/thread
  reaction controls one single-flight request, one globally unique mutation
  revision, and lifecycle-independent authoritative/rollback settlement.
- [x] Wagtail's current database search backend configured for PostgreSQL FTS
  with the multilingual `simple` configuration and SQLite FTS5 test fallback.
- [x] Blog search weights fixed at title 10, excerpt 7, body 4, and related tag
  names 2, with meaningful StreamField text extraction and service values
  excluded.
- [x] `/api/v1/posts/` now combines bounded Unicode `q`, exact Unicode `tag`,
  page, and page-size parameters under the canonical live-only policy.
- [x] `/api/v1/tags/` returns stable live-only distinct post counts without
  per-post/per-tag queries.
- [x] Search/tag pagination stays relative, retains active parameters, uses
  relevance plus `-pk` for search, and preserves publication ordering without
  a query.
- [x] The Feed is URL-driven for query, tag, and page; it includes accessible
  submit/clear controls, semantic active tags, safe URL serialization,
  noindex variants, and distinct invalid/empty/unknown/out-of-range/error
  states.
- [x] Every Feed list/search/filter/tag-count request keeps the existing
  `posts` cache tag; publication reindexes tags after cluster relations commit
  and uses the existing signed revalidation flow.
- [x] Separate `subscriptions` app added with constrained/protected Subscriber,
  EmailOutbox, EmailDelivery, EmailWebhookEvent, and HMAC-keyed anonymous
  rate-limit persistence.
- [x] Trim/casefold/IDNA email normalization, case-insensitive database
  uniqueness, 48-hour versioned purpose-bound confirmation, revocable
  unsubscribe, cooldown, resubscribe, and non-bypassable suppression added.
- [x] JSON-only same-origin CSRF APIs added for subscribe, confirm, and
  unsubscribe with generic 202 enumeration resistance and `Retry-After`
  database limits for anonymous email/IP scopes.
- [x] First-public-publication outbox trigger added with one-event database
  uniqueness, immutable audience cutoff, and draft/future/republish/restricted
  exclusions including due Wagtail scheduled publication.
- [x] Bounded email worker added with PostgreSQL skip-locked claims, stale
  reclaim, unique delivery creation, capped exponential retry, terminal
  failure, per-delivery UUID idempotency keys, and a 23-hour ambiguity guard
  under Resend's 24-hour key retention.
- [x] Replaceable memory/Resend adapters and escaped multipart confirmation and
  publication templates added; publication mail contains title, excerpt,
  canonical URL, normal unsubscribe, and RFC 8058 one-click headers.
- [x] Bounded raw-body Svix webhook verification, replay window, durable event
  ID deduplication, provider-message-only lookup, out-of-order-safe delivered /
  bounce / complaint state, and subscriber suppression added without raw
  provider payload retention.
- [x] Read-only Django Admin history plus explicit unsubscribe/suppress/
  unsuppress actions added with hard delete disabled.
- [x] Accessible Feed/post forms and explicit fragment-credential confirmation
  and unsubscribe pages added with generic states, CSRF, no browser
  persistence, noindex/no-referrer, exact rewrites, and Draft Mode exclusion.

## Milestone transition

Milestone 9 is complete at the application boundary. Django owns anonymous
subscriber lifecycle, credentials, CSRF/rate limits, durable publication and
delivery work, provider adaptation, webhook authentication/idempotency, and
administrative state. Next.js owns accessible forms and explicit human
confirmation/unsubscribe presentation without receiving a secret or internal
Django origin. Existing content/search/preview/revalidation/OAuth/discussion
contracts remain intact.

### Next recommended session

Milestone 10: isolated staging/production infrastructure.

Scope:

1. Add the production Django, Next.js standalone, and email-worker services.
2. Wire exact Nginx same-origin routes and environment isolation.
3. Configure staging Resend/DNS/webhook values and a bounded worker schedule.
4. Prove PostgreSQL locking and complete staging browser/provider smoke tests
   before any production cutover.

Out of scope for that session:

- production deployment or promotion;
- production DNS, OAuth, Resend, GitHub Environment, or secret changes;
- search/reaction redesign or custom emoji;
- deletion of legacy reference files.

### Exit criteria

- Staging/production services and data are isolated.
- Exact same-origin routing preserves CSRF/OAuth/webhook boundaries.
- Worker scheduling and monitoring are operational in staging.
- PostgreSQL/browser/provider behavior is verified without changing production.

## Milestone queue

- [x] Milestone 1 — repository foundation and Django/Wagtail skeleton.
- [x] Milestone 2 — content pages, StreamField blocks, tags, media, revisions.
- [x] Milestone 3 — REST content API, preview, and cache revalidation.
- [x] Milestone 4 — Next.js shell, Feed, post renderer, and Bridge.
- [x] Milestone 5 — Google/GitHub OAuth and session integration.
- [x] Milestone 6 — comments and Slack-style threads.
- [x] Milestone 7 — post and comment reactions.
- [x] Milestone 8 — PostgreSQL search and tag filtering.
- [x] Milestone 9 — email subscriptions and durable outbox worker.
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
- OAuth applications and credentials have not been created or installed.
  Mocked Google/GitHub callbacks are verified, but live provider consent,
  cancellation, provider-side configuration, and staging/production callback
  routing still require external setup and smoke tests. Staging and production
  must use separate applications.
- Current Docker Compose names collide if both environments run on one server.
- The current deployment workflow rebuilds production rather than promoting an
  already-tested staging image.
- The new backend currently coexists at `backend/django/` so the legacy Docker
  build remains intact. A later infrastructure milestone must promote the new
  backend to the final image layout deliberately.
- Docker build, Docker Compose config, and PostgreSQL-backed migrations remain
  unverified because Docker and PostgreSQL server binaries are not available
  locally. The Compose file parses as valid YAML, and generated frontend output
  remains excluded from Docker contexts.
- PostgreSQL-only row-lock concurrency tests for rate-bucket creation and
  comment edit/delete and reaction toggle serialization exist but were skipped
  locally because the test database is SQLite. The production model was not
  weakened or imitated for SQLite.
- PostgreSQL search ranking/weight assertions exist but were skipped locally
  with the other PostgreSQL-only tests because no PostgreSQL or container
  runtime is installed. SQLite verifies fields, Unicode, visibility, filtering,
  validation, and pagination but is not represented as PostgreSQL ranking.
- Browser runtime setup and troubleshooting succeeded, but no in-app Browser or
  Chrome backend was connected. Feed checks at 375x812 and 1440x900, real
  keyboard focus order, Back/Forward restoration, and visual empty/pagination
  states remain unverified rather than simulated.
- Legacy migrations contain resets and multiple heads and should not be reused
  as the new baseline.
- Email DNS records, verified Resend sender domains, webhook registrations,
  provider credentials, GitHub Environment values, and an actual worker
  schedule remain deliberately unconfigured. `docs/email-setup.md` is the
  external checklist.
- Email history and rate-limit buckets do not yet have an operational retention
  command. This belongs with worker monitoring/retention infrastructure.

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

2026-07-27:

- Milestone 9 official-source review covered Resend send/idempotency,
  Svix-compatible raw-body webhook verification and replay handling,
  delivered/bounced/complained events, transactional List-Unsubscribe, and
  SPF/DKIM/DMARC guidance. No live provider or DNS state was changed.
- `python3 -m uv lock --check` passed: 68 packages resolved. Ruff format check
  passed for 124 files, Ruff lint passed, the Django test-settings system check
  passed, and `makemigrations --check --dry-run` reported no drift.
- Full `pytest` passed: 393 tests; six PostgreSQL-only concurrency/search tests
  skipped honestly on SQLite. Subscription coverage includes normalization and
  constraints, enumeration resistance, CSRF/rate limits, credential lifecycle,
  publication exactly-once/cutoff exclusions, claim/reclaim/retry/idempotency,
  adapter failures, webhook authentication/replay/body limits, suppression,
  query counts, admin policy, migration state, and safe command output.
- A new empty SQLite database applied the complete migration chain. The new
  `subscriptions.0001_initial` migration then reversed to zero and applied
  forward again. Production `manage.py check --deploy` passed with safe
  non-production verification values; one intentional Wagtail iframe warning
  remains silenced.
- `npm ci` was not rerun because neither Node manifest nor lockfile changed.
  Prettier, ESLint, TypeScript, and full Vitest passed: 150 tests in 15 files.
  Production Next.js 16.2.11 build passed after the sandbox allowed
  Turbopack's local CSS worker port; `npm audit` reported zero vulnerabilities.
- Post-build `.next/static` scan found no internal Django origin, Resend or
  subscription secret names/values, build-time verification value, test
  credential, or email address.
- Browser runtime setup and its required troubleshooting/list probe found no
  connected Browser or Chrome backend, so 375x812/1440x900 visual, keyboard,
  and screen-reader browser QA did not run.
- Docker, PostgreSQL, `psql`, `postgres`, and `pg_isready` are unavailable.
  PostgreSQL skip-locked/reclaim concurrency tests remain present but were
  skipped; SQLite is not represented as PostgreSQL verification.
- The local Obsidian Stage 10 application checklist was updated. Real Resend
  credentials, SPF, DKIM, and DMARC remain open as external setup.
- Official Wagtail 7.4.2 documentation confirmed
  `wagtail.search.backends.database`, `django.contrib.postgres`, PostgreSQL's
  four effective weights, RelatedFields behavior, auto-update signals, and the
  need to run `update_index` after search configuration changes.
- `python3 -m uv lock --check` passed: 53 packages resolved with no dependency
  changes. `npm ci` was not rerun because neither Node manifest nor lockfile
  changed.
- Ruff format check and lint, Django test-settings system check, and
  `makemigrations --check --dry-run` passed with no migration drift.
- Full `pytest` passed: 340 tests; four PostgreSQL-only tests skipped on SQLite,
  including the new weight/ranking assertion. Search coverage includes every
  indexed field, English/Russian/mixed Unicode, combined filters, all hidden
  lifecycle states, tag counts, query-count stability, reindex-on-retag,
  relative pagination, malformed/repeated/bounded queries, and unknown tags.
- A new empty SQLite database applied the complete migration chain through all
  project and Wagtail 7.4 migrations. No project migration was added. The
  Wagtail `update_index` command then rebuilt 15 seeded SQLite objects.
- Production `manage.py check --deploy` passed with safe non-production
  verification values; one intentional Wagtail iframe warning remains
  silenced.
- Prettier, ESLint, TypeScript, and full Vitest passed: 137 tests in 14 files.
  Feed coverage includes URL parsing/serialization, Unicode single encoding,
  search submit/clear, tag select/clear, filter-preserving pagination,
  invalid/unknown/no-result/out-of-range distinctions, backend 404 versus
  infrastructure failure, noindex/canonical behavior, and shared `posts`
  cache tags.
- Production Next.js 16.2.11 build passed after the sandbox allowed
  Turbopack's local CSS worker port. `/` remains a dynamic server-rendered
  route. `npm audit` reported zero vulnerabilities.
- Post-build `.next/static` scan found no internal Django origin, verification
  secret, credential names, session identifier, or `X-Session-Token`.
- A temporary local SQLite-backed Django/Next production stack served `/`,
  `/api/v1/posts/`, and `/api/v1/tags/`; it was stopped after the probe.
- Browser runtime discovery and the required troubleshooting probe returned no
  connected Browser or Chrome backends, so responsive/keyboard visual QA did
  not run.
- Docker, PostgreSQL, `psql`, `postgres`, and `pg_isready` are unavailable.
  PostgreSQL search ranking and migration execution were not represented as
  verified.

2026-07-26:

- `python3 -m uv lock --check` — passed with a writable temporary uv cache; 53
  packages resolved and no dependency files changed.
- Ruff format/check, Django test-settings system check, and
  `makemigrations --check --dry-run` — passed.
- Full `pytest` — passed: 318 tests; three PostgreSQL-only concurrency tests
  skipped on SQLite. Remediation coverage proves lone/mixed surrogates become
  `ValidationError` across the validator, model save, Wagtail setting save, and
  raw JSON toggle API, with a stable JSON 400 and no encoding/HTML 500.
- A new empty SQLite database applied the complete migration chain; the new
  `discussions.0002` migration was then reversed to `0001` and reapplied.
- Production `manage.py check --deploy` — passed with safe non-secret
  verification values; one intentional Wagtail iframe warning remains silenced.
- `npm ci` was not rerun for the second remediation because neither dependency
  manifest nor lockfile changed; the existing lock remains the verified
  210-package install under Node.js 24.18.0 and npm 11.16.0.
- Prettier, ESLint, TypeScript, and full Vitest — passed: 125 tests in 13 files.
  The second remediation adds cross-instance coverage for one shared request
  and unique coordinator revisions, per-target independence, and closing the
  thread before either authoritative success or network rollback. In both close
  cases the parent settles and accepts a later fresh thread aggregate without
  an unmounted-component state update.
- Production Next.js build — passed with safe public/verification configuration
  after running outside the sandbox so Turbopack could bind its local CSS
  worker port.
- `npm audit` — passed against the registry with zero vulnerabilities.
- Post-build `.next/static` scan found no internal Django origin, verification
  secret, provider credential name, session identifier, or `X-Session-Token`.
  The roughly 424 KiB picker dataset is emitted as a lazy chunk and is absent
  from the initial post-page entry.
- Browser runtime discovery and the required troubleshooting probe returned no
  connected Browser or Chrome backends. The live close-during-pending-root-
  reaction scenario and responsive/interaction QA could not run.
- Docker and PostgreSQL server binaries remain unavailable. PostgreSQL locking
  semantics, concurrency tests, and Compose integration were not represented as
  verified.

Milestone 5 verification remains recorded below:

- `python3 -m uv lock --check` — passed; 52 packages resolved.
- `ruff format --check .` — passed (67 files); `ruff check .` — passed.
- Django test-settings system check and
  `makemigrations --check --dry-run` — passed; no schema drift.
- Full `pytest` — passed; 248 tests. The remediation matrix exercises every
  malicious return-to value through the helper and real django-allauth POST,
  stored state, and mocked callback for both Google and GitHub. Triple/multiple
  slash, encoded/double-encoded network paths, backslashes, raw/encoded
  controls, absolute/scheme URLs, malformed percent escapes, service routes,
  and extra slug segments all fall back to `/`.
- Production settings tests cover each of the four OAuth variables when
  missing, empty, space-only, tab-only, and newline-only; accidental outer
  whitespace is trimmed, both provider `APPS` must exist, and credential values
  do not appear in errors or captured output. Provider timeout coverage rejects
  zero, negative, NaN, infinity, empty/whitespace, and nonnumeric values while
  accepting a whitespace-padded finite positive number.
- Related regressions remain covered: POST-only social login, no retained
  `SocialToken`, verified-email-only linking, identity ownership, CMS/Admin
  password login, private/no-store current-user responses, CSRF logout, session
  rotation, `__Host-` cookies, one-proxy trust, and owner promotion.
- Empty-file SQLite migration passed through all Django, Wagtail,
  `wagtail_headless_preview.0001_initial`, blog, allauth `account.0009`, and
  `socialaccount.0006` migrations. The six socialaccount migrations also
  reversed to zero and applied forward again. The remediation creates no
  project-owned schema migration.
- Production `manage.py check --deploy` with safe non-secret verification
  values — passed; the
  Wagtail-required `X_FRAME_OPTIONS=SAMEORIGIN` warning is intentionally
  silenced.
- Node.js 24.18.0 and npm 11.16.0 were selected through fnm.
- `npm ci` was not rerun because neither dependency manifest nor lockfile
  changed during remediation.
- `npm run format:check`, `npm run lint`, and `npm run typecheck` — passed.
- Full `npm test` — passed; 76 Vitest tests in 11 files. Frontend parity now
  covers the same triple/multiple slash, encoded path, backslash, control,
  malformed-percent, scheme, service-route, and extra-path attacks and confirms
  that every fallback remains on the base origin.
- `npm run build` — passed with Next.js 16.2.11 and React/React DOM 19.2.8;
  Feed, posts, login, and account are dynamic server routes; Bridge remains
  statically rendered; Draft Mode and revalidation routes remain present.
- `npm audit` — passed; zero vulnerabilities.
- A post-build browser-asset scan passed with no internal Django origin,
  credential names, build-time verification value, or `X-Session-Token` under
  `.next/static`; auth source modules contain no browser-stored token path.
- In-app Browser discovery returned no available browser backends. Screenshot
  QA of login return-to and the user menu could not run.
- Docker, PostgreSQL server binaries, and `pg_isready` are not installed, so
  Docker/Compose and PostgreSQL-backed migrations/session/OAuth checks were not
  run. SQLite results are not represented as PostgreSQL or container
  verification.
- Real Google/GitHub credentials were not used. Live consent, provider-hosted
  cancellation screens, staging callbacks, and production callbacks were not
  tested; all provider HTTP/callback automation used mocks.
