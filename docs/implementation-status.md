# Implementation status

Last updated: 2026-07-28

Integration branch: `rewrite/wagtail-next`

Overall state: Milestone 11 testing and security hardening is implemented at
the repository boundary with explicit PostgreSQL/Compose/Playwright CI gates,
upload and interaction boundary hardening, and deterministic four-viewport
browser coverage; external staging activation, live providers, production
deployment, and unavailable local Docker/Nginx/PostgreSQL checks remain pending

## Current repository state

- The `main` branch contains the deployed legacy Flask/React implementation.
- The legacy database and Alembic history are experimental.
- The new Django/Wagtail backend is isolated under `backend/django/`.
- The public Next.js application is isolated under `frontend/next/`; the legacy
  Vite frontend remains unchanged.
- Legacy Flask/Vite source and Docker files remain reference material, but no
  active Compose or GitHub Actions entrypoint builds or deploys Flask.
- The root `docker-compose.yml` delegates to the Django/Next local development
  stack in `compose.dev.yml`.
- Production infrastructure lives under `infra/`; one edge Compose project
  fronts isolated staging and production application projects.
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
- [x] Milestone 9 remediation snapshots message schema/FROM/origin/subject and
  publication inputs on the outbox plus recipient/credential issue inputs on
  each delivery; the exact compact Resend JSON fingerprint gates every retry
  without persisting a raw signed credential.
- [x] Provider ambiguity now starts at immutable
  `first_provider_attempt_at`, remains independent of mutable reclaim leases,
  and enters explicit `manual_review` without provider I/O at the absolute
  23-hour safety deadline or on payload mismatch.
- [x] Resend response reads are bounded and official 409 variants are split:
  `invalid_idempotent_request` is terminal,
  `concurrent_idempotent_requests` is retryable, and unknown conflicts are
  conservatively terminal without persisting provider bodies.
- [x] Authenticated recognized webhooks can wait durably for provider-ID
  correlation, apply deterministically after worker settlement, suppress on
  early bounce/complaint, and expire through a bounded seven-day
  correlation/30-day retention command without storing raw payloads.
- [x] Unsubscribe skips only unclaimed delivery work; row-locked settlement
  records an accepted in-flight call honestly while the subscriber remains
  unsubscribed and excluded from every later claim/publication.
- [x] Publication delivery rechecks the canonical visibility policy immediately
  before its first provider call and skips unpublished, expired, restricted,
  future-scheduled, or no-longer-public posts without mutating the immutable
  email snapshot.
- [x] The second Milestone 9 remediation makes `EMAIL_FROM_ADDRESS` a
  provider-independent, normalized, mandatory production message input while
  keeping Resend API/webhook credentials conditional on the Resend adapter.
- [x] Provider adapters now fingerprint their own exact deterministic request
  bytes before I/O; Resend uses those bytes as its HTTP body, memory remains
  local/test-only, and a replacement adapter must implement the same explicit
  serialization boundary.
- [x] The third Milestone 9 remediation pins adapter contract identifier,
  serializer contract version, and non-secret idempotency namespace on every
  delivery; any provider/account/environment/version drift enters
  `manual_review` before provider I/O even when body bytes match.
- [x] Provider preparation now serializes exactly once per attempt into a
  frozen bounded request; worker verification and Resend
  `urllib.request.Request.data` use those same bytes, and `send()` cannot
  reconstruct a body from mutable message inputs.
- [x] Snapshot boundaries now store the full 265-character maximum publication
  subject and long Unicode-slug fallback URLs without truncation, with
  deterministic fail-fast limits independent of SQLite varchar behavior.
- [x] `subscriptions.0002_harden_email_delivery` adds the snapshot,
  fingerprint, ambiguity, manual-review, webhook-correlation, constraint, and
  reconciliation indexes without modifying `0001_initial`; before any
  push/deployment it was amended to create sender/subject at 512 characters and
  post URL as text before its existing-data backfill.
- [x] Additive `subscriptions.0003_bind_delivery_transport_identity` preserves
  terminal legacy history under an explicit marker and quarantines legacy
  `pending`/`processing` rows as `manual_review`; its reverse data operation
  safely reduces retryable rows and transport-specific mismatch reasons to the
  `0002`-compatible `manual_review`/`payload_mismatch` quarantine before
  restoring old constraints.
- [x] ADR 0005 fixes one host-port-owning edge project plus separate staging
  and production application projects, networks, volumes, databases, aliases,
  S3/provider namespaces, and secrets without `container_name`.
- [x] Production non-root Django/worker, Node 24 Next standalone, and Nginx
  edge images added with locked dependencies, exec-form commands, liveness
  checks, immutable runtime filesystems, and no build-time production secrets.
- [x] Runtime-dynamic Next metadata and routes allow one standalone artifact to
  run with staging and production origins without embedding either origin or
  the internal Django URL in browser assets.
- [x] Exact edge routes preserve Next Draft Mode/revalidation exceptions,
  Django session/CSRF/OAuth/API ownership, S3 media redirects, immutable
  collectstatic assets, trusted forwarding headers, and narrow staging Basic
  Auth exceptions.
- [x] Production S3-compatible Wagtail media storage added with separate
  static/media backends, fail-fast environment validation, absolute public
  URLs, and filesystem storage retained for local/test.
- [x] One bounded management-command scheduler per environment independently
  runs scheduled publishing, revalidation, email delivery, and webhook
  reconciliation with structured output, capped backoff, SIGTERM, and atomic
  heartbeat.
- [x] Immutable release manifests, build-once digest publication, gated staging
  rollout, staging attestation, and manual no-rebuild production promotion
  replace the active Flask and migration-generation workflows.
- [x] CI retains a fast SQLite job and adds PostgreSQL concurrency/search plus
  empty/reverse/forward migration checks, frontend/audit/build checks, image
  builds, Compose isolation, Nginx validation, and container smoke.
- [x] Repository scripts and runbooks cover bounded secret transfer, migration
  order, custom-format PostgreSQL backup/integrity/retention, scratch-first
  restore, staging drills, and image/database rollback separation.
- [x] Milestone 10 remediation separates database/application/egress/edge
  networks; worker outbound no longer depends on edge and integration has an
  egress-only HTTP provider regression.
- [x] Database-only Compose owns bootstrap/backup/restore without Django/Next
  image interpolation; restore authenticates required metadata and SHA-256
  before `createdb`, and first production backs up pinned PostgreSQL before its
  first migration or public application start.
- [x] Docker DNS, shared upstream zones, and resolving Nginx 1.29 servers remove
  stale container IPs and keep absent staging/production hosts independent.
- [x] Raw role-scoped control/PostgreSQL/Django/worker/Next env contracts
  preserve bounded single-line bytes while preventing cross-service secret
  exposure; Docker Compose 2.30.0 is the explicit minimum.
- [x] Rollout is backup-first, one-migration, bounded-wait, readiness/health/
  heartbeat/egress/digest gated and two-phase. Versioned bundles/runtime,
  cross-workflow/server locking, and monotonic staging sequences make
  activation and rollback independent of a server Git checkout.
- [x] Milestone 10 rollout-state remediation uses one fsynced atomic
  `rollout-state.json`, immutable operation IDs/manifests, idempotent finalize,
  exact application/edge component snapshots, retained failure evidence, and
  explicit reviewed abort/recovery. First bootstrap refuses an unbound existing
  PostgreSQL volume and resumes only the recorded attempt; backup metadata
  distinguishes initial-empty, pre-migration, recovery, and manual evidence.
- [x] The remaining Milestone 10 bootstrap crash gap is closed: authorization
  is durable before an explicit labeled `docker volume create`, PostgreSQL
  Compose treats the volume as external, exact environment/role/bootstrap
  operation/volume labels are verified on every use, authorized absence may
  resume, and confirmed-ready disappearance or foreign adoption fails closed.
- [x] Schema-3 `rollout-state.json` owns a database snapshot independent of
  active application state, including absent/authorized/ready/migrated
  lifecycle, volume/PostgreSQL/bootstrap identity, initial/last backup, and the
  latest confirmed migration boundary.
- [x] Idempotent bounded failure evidence now closes every in-progress runtime
  phase, releases the mutation lease, preserves candidate/base/database and
  possible-side-effect snapshots, and transfers reviewed ownership to active-A
  recovery, exact-candidate retry, or new-release fix-forward. Failed first
  deployments remain recoverable with `active=null`; fix-forward takes a
  recovery backup and cannot repeat initial-empty backup over an existing DB.
- [x] CI remote rollout failure handling records evidence under the server lock
  without replacing the original exit status; active-A internal recovery and
  first-deploy retry/fix-forward repeat application, edge, health, and public
  gates before idempotent finalize.
- [x] The final two Milestone 10 resolution defects are closed: retry and
  fix-forward accept a reviewed deployment sequence outside immutable runtime,
  bind it to their operation ID, and preserve runtime bytes; schema-3 attempts
  carry deep-validated activation policy so recovery retry lineages preserve
  previous while deploy/rollback/fix-forward lineages rotate active to
  previous.
- [x] Milestone 11 began with the baseline coverage matrix in
  `docs/testing-security.md`; existing post/comment/thread/reaction/auth/
  subscription and infrastructure proofs are reused rather than duplicated.
- [x] Backend security gaps now cover CSRF-cookie-secret mismatch and
  cross-origin CSRF (without incorrectly binding standard Django CSRF to the
  login session), expired sessions, forbidden Unicode scalars,
  site-author/owner/moderator
  permissions, upload format/size/pixel limits, and metadata-free image
  originals.
- [x] PostgreSQL search, comment/reaction/rate-limit locking, and outbox claim
  races are an explicit marker-selected CI suite; `PYTEST_FAIL_ON_SKIP=1`
  turns any PostgreSQL skip into a required-job failure.
- [x] The fast Playwright browser-contract matrix exercises anonymous reading,
  mock Google/GitHub login, comments/threads/reactions, subscription
  confirmation and unsubscribe, Draft Mode isolation, Feed
  search/tags/pagination, keyboard traps/Escape/focus restoration, and axe at
  375x812, 768x1024, 1440x900, and 1920x1080.
- [x] A separate required cross-stack Playwright suite uses real Django API
  views, SQLite database sessions, standard CSRF, Next rewrites, and
  persistence for Google/GitHub allauth callbacks, comment/reply/reaction,
  subscription confirm/unsubscribe, and Draft Mode. Only OAuth provider and
  email-transport inspection boundaries are test doubles; no production URL or
  production setting includes a test helper.
- [x] Browser screenshots and traces are failure-only, video is disabled, and
  retained artifacts are streamed and scanned (including ZIP entries and raw
  image bytes) for Playwright URL/JSON cookie/header representations, OAuth and
  signed credentials, provider sentinels, secret names, and internal origins.
  Plain/ZIP/entry/count/declared/actual limits, encryption, corruption, and
  short reads fail closed without whole-file decompression. Unsafe files are
  removed before a second scan. Upload still requires
  `artifacts.outcome == success`; any enumeration/ZIP/read/removal/scanner
  failure skips upload and fails CI. Raw binary string search is not represented
  as visual pixel/OCR inspection.
- [x] CI retains the exact Next.js proxy allowlist without a broad `/api/*`
  rewrite, runs the full Compose/Nginx/PostgreSQL/backup-recovery/MinIO/egress/
  restart suite, and exposes one `ci-required` result that fails unless every
  mandatory Milestone 11 job succeeds.

## Milestone transition

Milestone 11 testing and security hardening is complete at the repository
boundary. It did not activate staging, perform the functional launch, redesign
the public UI, deploy production, or change server, registry, DNS, TLS, OAuth,
Resend, GitHub Environment/secret, bucket, or production data state.

### Next recommended session

Functional staging acceptance (product checklist Stage 13), only after the
external staging activation checklist is completed.

Scope:

1. Activate the protected staging environment and required external namespaces.
2. Run the repository container/PostgreSQL/Nginx smoke checks on the target
   runtime.
3. Complete real staging OAuth, Resend, S3, authoring, scheduled publication,
   backup/restore-drill, and rollback rehearsal.
4. Reconcile every failed or unavailable check before considering production.

Out of scope for that session:

- production promotion or data migration;
- search/reaction redesign or custom emoji;
- deletion of legacy reference files.

### Exit criteria

- Staging runtime passes all container and PostgreSQL checks.
- OAuth, Resend, S3, media, Draft Mode, and signed revalidation pass on staging.
- Backup/restore and compatible image rollback are rehearsed.
- The same release SHA passes the already-required 375x812, 768x1024,
  1440x900, and 1920x1080 browser matrix in CI.

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
- [x] Milestone 10 — isolated staging/production infrastructure.
- [x] Milestone 11 — testing and security hardening.
- [ ] Functional staging acceptance and launch.
- [ ] Milestone 12 — visual design and polish.

## Known risks

- The Next.js duplicate-event registry is process-local. Duplicate invalidation
  remains safe across processes because tag/path invalidation is idempotent.
- Preview snapshot and delivered revalidation event retention are currently
  bounded only by opportunistic preview cleanup and database operations; a
  formal operations retention command belongs with worker infrastructure.
- The bounded worker runtime is repository-owned but has not run under Docker
  or against PostgreSQL locally; operational heartbeat/alerting still needs
  staging verification.
- S3-compatible media settings are implemented, but buckets, credentials,
  public origins, versioning, lifecycle, CORS, and restore behavior remain
  external activation work.
- OAuth applications and credentials have not been created or installed.
  Mocked Google/GitHub callbacks are verified, but live provider consent,
  cancellation, provider-side configuration, and staging/production callback
  routing still require external setup and smoke tests. Staging and production
  must use separate applications.
- Docker build, Docker Compose config, and PostgreSQL-backed migrations remain
  unverified locally because Docker and PostgreSQL server binaries are not
  available. YAML parsing and route-contract tests are not represented as
  Docker Compose, image, Nginx, PostgreSQL, or integration-runtime verification.
- Seven PostgreSQL-only search/locking/concurrency cases were deselected from
  the local SQLite run because no PostgreSQL or container runtime is installed.
  They run in a dedicated CI selection where any skip fails the job; the
  production model was not weakened or imitated for SQLite.
- Local Chromium passed the complete deterministic Playwright matrix at all
  four required viewports. This proves repository browser behavior against
  mock providers, not live staging OAuth/Resend/S3, target Nginx, or production
  data.
- Legacy migrations contain resets and multiple heads and should not be reused
  as the new baseline.
- The shared edge cannot be replaced independently per application environment;
  a changed edge digest requires a production-approved host-wide operation
  compatible with both live application versions.
- A server carrying superseded multi-file
  `active-release.json`/manifest/pending state or schema-2
  `rollout-state.json` must not be auto-adopted. The schema-3 loader fails
  closed and requires a reviewed one-time migration before any rollout; no
  external server state was changed in this repository session.
- Email DNS records, verified Resend sender domains, webhook registrations,
  provider credentials, GitHub Environment values, and staging activation
  remain deliberately unconfigured. `docs/email-setup.md` and
  `docs/staging-activation-checklist.md` are the external checklists.
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

2026-07-28:

- Final Milestone 11 point remediation expands the retained-artifact scanner to
  real Playwright URL, cookie, header, OAuth, provider-boundary, preview, and
  signed subscription credential representations. Seventy-six scanner
  regressions passed: every representation is exercised as a plain artifact and
  ZIP entry, realistic `trace.trace`/`trace.network` fixtures are included, all
  four injected operational failures fail closed, and ZIP/plain preflight plus
  streamed actual limits cover oversized, encrypted, corrupt, short, and
  boundary-split inputs.
- An intentionally failing cross-stack test with trace retention created a real
  credential-bearing Playwright 1.62 trace. Sanitization removed its trace ZIP
  and credential-bearing error context, retained only the byte-safe screenshot,
  and the second scan passed. The unchanged CI upload condition is regression
  tested to require `artifacts.outcome == success`, so the unsafe original
  cannot reach `upload-artifact`.
- Wagtail image upload now converts Pillow/Willow parsing, malformed EXIF,
  decode, and encode failures into form `ValidationError` responses. Twenty-seven
  targeted upload/security tests passed, including real Wagtail admin
  JPEG/PNG/WebP uploads, malformed JPEG/WebP EXIF, truncated/corrupt files,
  metadata stripping, format/extension, size, pixel, and animation boundaries.
  PDF upload is explicitly extension-and-size-only; actual PDF bytes are not
  parsed or attested.
- The former mock-backend Playwright suite is now the explicitly named
  browser-contract suite and passed 20/20 runs at all four required viewports.
  The new cross-stack suite passed 4/4 against real Django API views, SQLite
  database sessions, standard CSRF, Next rewrites, and persistence for
  Google/GitHub allauth callbacks, comments/replies/reactions, memory-transport
  subscription confirmation/unsubscribe, and Draft Mode. No test helper URL or
  production setting was added.
- `uv lock --check` resolved 74 packages; Ruff format/lint, Django test and
  production deploy checks, migration drift, a clean empty SQLite migration
  chain, and subscriptions/discussions reverse-forward checks passed. Full
  backend `pytest` passed 506 tests with seven PostgreSQL-only cases skipped on
  SQLite.
- The PostgreSQL marker selection was deliberately run with
  `PYTEST_FAIL_ON_SKIP=1` and failed because all seven cases skipped: Docker,
  Podman, PostgreSQL server/client, `pg_isready`, and Nginx remain unavailable
  locally. PostgreSQL/Compose/Nginx results are not inferred; the PostgreSQL CI
  service retains the no-skip gate and `ci-required` requires it.
- Deterministic infrastructure verification passed 208 pytest cases plus shell
  syntax and Python compilation. Prettier, ESLint, TypeScript, 152 Vitest
  tests, the production Next.js build, two standalone runtime-origin probes,
  and browser-asset scanning passed.
- Milestone 11 coverage audit recorded the pre-change 480 backend, 152 Vitest,
  and 131 infrastructure cases. The completed local SQLite selection passed
  486 tests with seven PostgreSQL cases deliberately deselected; Ruff format/
  lint, Django check, migration drift, and the targeted security suite passed.
- Playwright 1.62.0 with Chromium passed 20/20 critical-flow runs: five flows
  at each of 375x812, 768x1024, 1440x900, and 1920x1080. Axe, keyboard trap,
  Escape/focus restoration, mobile full-screen thread, mock Google/GitHub,
  subscriptions, Draft Mode isolation, and feed controls are included.
- Frontend format, ESLint, TypeScript, 152 Vitest tests, production Next.js
  build, and `npm audit --audit-level=high` (zero vulnerabilities) passed.
  Turbopack build and browser servers required the approved loopback sandbox
  exception.
- Deterministic infrastructure verification passed 132 pytest cases plus shell
  syntax and Python compilation. Docker, Compose, Nginx, PostgreSQL, `psql`,
  and `pg_isready` remain unavailable locally; their full suite is required by
  `ci-required` and is not claimed as locally executed.
- Exact-candidate retry now receives a positive reviewed sequence explicitly
  through `resolve_failed_rollout.sh`; ordinary CI still reads rendered
  `DEPLOY_SEQUENCE`. Shell regression invokes the real resolution entrypoint
  with failed runtime sequence N, accepts N+1, preserves every runtime byte,
  rejects N and conflicting N+2, and proves the identical operation/sequence
  begin is byte-preserving.
- Schema-3 attempts now record `activation_policy`. Recovery and recursive
  recovery retries preserve previous; deploy, rollback, fix-forward, and their
  retries rotate active to previous. Deep validation rejects policy/lineage
  tears and identical active/previous component snapshots. Coverage includes
  one and two failed recovery retries, a new recovery, recovery fix-forward,
  failed rollback retry, and duplicate finalize.
- `backend/django/.venv/bin/python -m pytest -q infra/tests` passed 131
  regressions. Shell syntax, Python compilation, Ruff format/lint, and
  `git diff --check` passed.
- Full backend SQLite `pytest` passed 474 tests with six PostgreSQL-only
  concurrency/search skips. `uv lock --check` resolved 74 packages; Django
  test and production deploy checks, migration drift, and a complete empty
  SQLite migration chain passed.
- Node.js 24.18.0/npm 11.16.0 frontend format, ESLint, TypeScript, 152 Vitest
  tests in 16 files, production Next.js 16.2.11 build, and standalone
  staging/production runtime-origin probes passed. Build and standalone probes
  required the approved local loopback-port exception after the sandbox
  rejected their binds.
- Browser-asset and tracked-diff credential-pattern scans passed; gitleaks and
  TruffleHog are unavailable locally. Docker, Compose, Nginx, PostgreSQL,
  `psql`, and `pg_isready` are unavailable, so container/Compose/Nginx/
  PostgreSQL runtime tests were not run and are not inferred from deterministic
  tests. No push, deployment, or external state change was performed.

2026-07-27:

- The final Milestone 10 recovery-gap remediation advances the sole fsynced
  authoritative document to schema 3 with operation-owned volume labels,
  database lifecycle/backup/migration truth independent of active application,
  bounded idempotent failure evidence, and reviewed recovery/retry/fix-forward
  ownership. Fault coverage spans every failure phase plus authorization atomic
  replace → volume create → container start → database-ready boundaries;
  container CI uses real Docker volumes for those three crash gaps.
- `backend/django/.venv/bin/python -m pytest -q infra/tests` passed 124
  deterministic infrastructure regressions. Shell syntax, Python compilation,
  Ruff format/lint, workflow/Compose contract parsing, remote-rollout
  original-status preservation, source/browser-asset secret and internal-origin
  scans, Obsidian checklist parity, and `git diff --check` passed.
- Full backend SQLite `pytest` passed 474 tests with six PostgreSQL-only
  concurrency/search skips. `uv lock --check` resolved 74 packages; Ruff,
  Django test-settings check, migration drift, a complete empty-SQLite
  migration chain, and production `check --deploy` passed.
- Node.js 24.18.0/npm 11.16.0 frontend format, ESLint, TypeScript, 152 Vitest
  tests in 16 files, and the Next.js 16.2.11 production build passed. The build
  required the already approved out-of-sandbox local Turbopack CSS worker port
  after the sandbox correctly rejected that bind.
- Docker/Compose, Nginx, PostgreSQL, `psql`, and `pg_isready` are unavailable
  locally. Therefore real Compose config, PostgreSQL/bootstrap/recovery, Nginx,
  and container integration were not run locally and are not inferred from
  deterministic tests. They remain mandatory in CI; no external or production
  state was changed.
- Milestone 10 rollout-state remediation replaced separate mutable
  active/current/previous/pending files with one mode-0600, fsynced, atomic
  schema-2 document. Immutable operation IDs, manifest fingerprints,
  phase-idempotent retries, duplicate-finalize no-op, component-specific
  application/edge truth, reviewed abort/recovery, and retained failed-smoke
  evidence are covered by fault injection before/after every unique atomic
  transition.
- First bootstrap now requires a newly absent volume or the same saved
  volume-authorization attempt, and purpose-typed metadata distinguishes
  `initial-empty`, `pre-migration`, `recovery`, and `manual` backups. Container
  CI exercises a real fault-interrupted PostgreSQL bootstrap/resume and rejects
  an existing unbound volume. MinIO initialization uses a bounded readiness
  retry.
- `backend/django/.venv/bin/python -m pytest -q infra/tests` passed 75
  deterministic infrastructure regressions. The full backend SQLite suite
  passed 474 tests with six PostgreSQL-only skips. Backend Ruff format/lint,
  Django system check, migration drift, a complete empty-SQLite migration
  chain, production `check --deploy`, `uv lock --check`, shell syntax, Python
  compilation, workflow YAML parsing, full-SHA Action pins, source and existing
  browser-asset secret/internal-origin scans, and `git diff --check` passed.
- Docker/Compose, Nginx, PostgreSQL server tools, Node, and npm are unavailable
  locally. Compose config, Docker integration, real `nginx -t`, PostgreSQL
  bootstrap/backup/recovery container tests, and frontend format/lint/
  typecheck/Vitest/build could not run locally and are not claimed. They remain
  mandatory CI jobs; no external deployment or infrastructure mutation was
  performed.
- Milestone 10 remediation added role-scoped raw environments, distinct
  database/application/egress networks, database-only operations, verified
  backup metadata, first-production bootstrap, dynamic Docker-DNS upstreams,
  health/digest-gated two-phase activation, durable current/previous release
  state, shared locking, rollback tooling, and expanded Docker CI coverage.
- `backend/django/.venv/bin/python -m pytest -q infra/tests` passed 33
  infrastructure regressions. Targeted production-settings and subscription
  outbox coverage passed 131 tests; the full SQLite suite passed 474 tests
  with six PostgreSQL-only skips. A fresh SQLite database applied the complete
  migration chain and migration drift was empty. `uv lock --check`, production
  `check --deploy`, Python compile, shell syntax, Ruff, workflow YAML parsing,
  and `git diff --check` passed during remediation.
- Node/npm are not installed in the local execution environment. The frontend
  source and dependency manifests were unchanged, but frontend format/lint/
  type/test/build/audit were unavailable and are not claimed as rerun.
- Docker is not installed locally (`docker: command not found`). Therefore the
  new Compose config matrix, Nginx 1.29 `nginx -t`, PostgreSQL
  backup/restore/bootstrap, MinIO, worker egress, dynamic DNS/container
  replacement, Basic Auth/forwarding, restart, and container secret-isolation
  suite are implemented in CI but were not claimed as locally passed.
- Milestone 10 adds ADR 0005, isolated application/edge Compose definitions,
  production Django/worker, Next standalone and edge images, exact same-origin
  routing, S3 Wagtail media, a bounded four-task worker, immutable release
  manifests, staging-attested manual promotion, PostgreSQL CI, and
  backup/restore/deployment runbooks. Active Compose and workflows no longer
  build or deploy Flask.
- `python3 -m uv lock --check` passed with 74 packages resolved. Ruff format
  check passed for 136 files, Ruff lint passed, Django test-settings system
  check and migration-drift check passed, and production `check --deploy`
  passed with safe non-production values and one intentional Wagtail iframe
  check silenced. Credential-free build settings collected 943 static files
  into a temporary immutable manifest tree.
- Targeted infrastructure/backend tests passed 107 tests. Full SQLite `pytest`
  passed 473 tests; six PostgreSQL-only locking/race/search tests skipped
  honestly. A fresh SQLite database applied the entire migration chain;
  `subscriptions.0003` and `discussions.0002` each reversed one migration and
  reapplied.
- Prettier, ESLint, TypeScript, and full Vitest passed: 152 tests in 16 files.
  The production Next.js 16.2.11 build passed, and every public/internal route
  is runtime-rendered. The same standalone artifact started successfully with
  staging and production `PUBLIC_SITE_URL` values. Browser assets contained no
  staging/production origin, internal Django URL, or secret-name markers.
  `npm audit --audit-level=high` reported zero vulnerabilities.
- Thirteen infrastructure contract/script tests, shell syntax, Python compilation,
  workflow/Compose YAML parsing, full-SHA action pin scan, legacy active
  entrypoint scan, release-manifest validation, and Nginx routing regression
  tests passed.
- Docker, Podman, Nginx, PostgreSQL, `psql`, and `pg_isready` are unavailable
  locally. Therefore image builds, `docker compose config`, simultaneous
  Compose runtime, `nginx -t`, PostgreSQL concurrency/migrations, container
  smoke/restart behavior, and live browser/provider/S3 flows were not run and
  are not inferred from YAML/unit results.
- No push, deployment, DNS/TLS, OAuth/Resend, GitHub secret/Environment,
  registry, S3 bucket, production backup/restore, or server-state action was
  performed.
- The third Milestone 9 remediation binds each delivery to a normalized
  adapter contract identifier, serializer contract version, and non-secret
  provider account/environment idempotency namespace. Provider/namespace/
  version drift and body mismatch now enter `manual_review` before I/O, while
  same-identity retries retain the delivery UUID key and absolute 23-hour
  window.
- Provider preparation returns one frozen bounded request. The worker hashes
  and verifies its body once per attempt and passes that same bytes
  object/value to transport; Resend supplies it directly as
  `urllib.request.Request.data` and cannot reserialize an `EmailMessage` inside
  `send()`.
- Additive `subscriptions.0003_bind_delivery_transport_identity` applied on a
  clean empty SQLite chain, reversed to `0002` and reapplied, and the complete
  subscriptions chain reversed to zero and reapplied. Populated migration
  coverage exercises `0002 -> 0003 -> 0002 -> 0003`, preserving sent provider
  IDs/timestamps while reducing former pending/processing rows and all four new
  mismatch reasons to the safe `manual_review`/`payload_mismatch` downgrade
  shape. A latest-state delivery with valid known identity is also quarantined
  rather than made retryable. `0001_initial`, the widened `0002`
  snapshot/FROM/URL remediation, model state, and migration drift remain
  unchanged.
- `python3 -m uv lock --check` passed with 68 packages resolved. Ruff format
  check passed for 130 files, Ruff lint passed, Django system check and
  `makemigrations --check --dry-run` passed, and production
  `check --deploy` passed for both Resend and the memory adapter without Resend
  credentials.
- The targeted provider/settings/subscriptions/migration suite passed 167
  tests. Full `pytest` passed 452 tests; six PostgreSQL-only concurrency/search
  tests skipped on SQLite. Docker, PostgreSQL, `psql`, `postgres`, and
  `pg_isready` are unavailable, so no PostgreSQL concurrency result is claimed.
- Prettier, ESLint, TypeScript, and full Vitest passed: 150 tests in 15 files.
  The production Next.js 16.2.11 build passed outside the sandbox because
  Turbopack's CSS worker requires a local port. `npm audit` reported zero
  vulnerabilities.
- The post-build `.next/static` scan found no internal Django origin,
  verification secret, Resend/subscription secret markers, adapter contract,
  serializer version, idempotency namespace, or provider fingerprint fields.
  No live browser/provider flow ran because the remediation changes no public
  API or UI and no external provider state was placed in scope.
- The local Obsidian checklist was updated outside Git. No push, deployment,
  DNS, Resend, OAuth, GitHub secret/Environment, or production infrastructure
  change was performed; Milestone 10 was not started.
- The second Milestone 9 remediation removed the Resend-specific FROM setting,
  made every successfully imported production adapter configuration carry a
  valid `EMAIL_FROM_ADDRESS`, and moved request fingerprints behind the
  adapter's exact-byte `serialize_request()` contract. Official Resend send,
  24-hour idempotency, and both documented 409 contracts were rechecked; no
  provider or external state changed.
- Boundary coverage proves a maximum 255-character Wagtail title yields the
  complete 265-character immutable subject, a maximum Unicode fallback URL can
  exceed 2,048 safely in text storage, invalid FROM values fail before the
  confirmation transaction commits, and a custom adapter hash matches its
  exact selected bytes. The production-like memory adapter test creates and
  processes a confirmation with no Resend credentials.
- `subscriptions.0002_harden_email_delivery` was amended because it remains
  unpushed/undeployed: its fields are widened before the data operation that
  could otherwise fail. A migration regression starts with an existing
  maximum-title publication event at `0001`, then verifies the full subject and
  long URL after `0002`. An empty SQLite database applied the clean chain;
  `0002` reversed to `0001_initial` and reapplied; drift remained empty.
- `python3 -m uv lock --check` passed with 68 packages resolved. Ruff format
  check passed for 129 files, Ruff lint passed, Django system check and
  `makemigrations --check --dry-run` passed, and production
  `check --deploy` passed with a non-Resend adapter and safe verification
  values.
- The targeted settings/outbox/migration suite passed 104 tests. Full `pytest`
  passed 428 tests; six PostgreSQL-only concurrency/search tests skipped on
  SQLite. Docker, PostgreSQL, `psql`, `postgres`, and `pg_isready` are
  unavailable, so SQLite is not represented as PostgreSQL verification.
- Prettier, ESLint, TypeScript, and full Vitest passed: 150 tests in 15 files.
  The production Next.js 16.2.11 build passed outside the sandbox because
  Turbopack's CSS worker needs a local port. `npm audit` reported zero
  vulnerabilities.
- The post-build `.next/static` scan found no internal Django build origin,
  build verification secret, Resend/subscription secret names or values,
  webhook/API-key shapes, provider payload fingerprint fields, or server-side
  credential/attempt fields. No live browser/provider flow ran because this
  audit changes no public API or UI and no Browser/provider environment was in
  scope.
- The local Obsidian Milestone 9 checklist was updated outside Git. No push,
  deployment, DNS, Resend, OAuth, GitHub secret/Environment, or production
  infrastructure change was performed; Milestone 10 was not started.
- Milestone 9 remediation now pins byte-stable provider inputs/fingerprint,
  separates provider ambiguity from worker leases, classifies both official
  Resend 409 variants, durably reconciles early webhooks, preserves honest
  in-flight unsubscribe state, and revalidates publication visibility before
  the first provider call. Official Resend idempotency, error, webhook
  delivery, ordering, and retry documentation was rechecked; no provider or
  external state changed.
- `python3 -m uv lock --check` passed with 68 packages resolved. Ruff format
  check passed for 127 files, Ruff lint passed, the Django test-settings system
  check passed, and `makemigrations --check --dry-run` reported no drift.
- Full `pytest` passed: 419 tests; six PostgreSQL-only concurrency/search tests
  skipped honestly on SQLite. The 71 subscription tests cover immutable
  rendering across time/post/config changes, fingerprint mismatch,
  official/unknown 409 classification, bounded responses, timeout/retry at
  hour 22, absolute deadline, sparse worker/crash reclaim, early
  delivered/bounce/complaint ordering and reconciliation, foreign retention,
  in-flight unsubscribe, visibility cancellation, model constraints, and
  migration reversal.
- A new empty SQLite database applied the complete migration chain through
  `subscriptions.0002_harden_email_delivery`; that migration reversed to
  `0001_initial` and reapplied. Production `manage.py check --deploy` passed
  with safe non-production verification values and one intentional Wagtail
  iframe check silenced.
- Prettier, ESLint, TypeScript, and full Vitest passed: 150 tests in 15 files.
  Production Next.js 16.2.11 build passed outside the sandbox because
  Turbopack's CSS worker requires a local port. `npm audit` reported zero
  vulnerabilities.
- The post-build `.next/static` scan found no internal Django build origin,
  Resend/subscription secret names or values, webhook secret shape, provider
  payload fingerprint fields, or server-side credential-version fields.
- Docker, PostgreSQL, `psql`, `postgres`, and `pg_isready` are unavailable.
  PostgreSQL skip-locked/concurrency tests remain present but were not run;
  SQLite is not represented as PostgreSQL verification. No live browser or
  provider flow was run because this remediation changes no public UI and no
  Browser/provider environment was placed in scope.
- The local Obsidian Milestone 9 checklist was updated outside Git. No push,
  deployment, DNS, Resend dashboard, GitHub secret/Environment, or production
  infrastructure change was performed.
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
