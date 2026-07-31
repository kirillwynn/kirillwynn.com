# Implementation status

Last updated: 2026-07-30

Integration branch: `rewrite/wagtail-next`

Overall state: Milestone 11 testing and security hardening is implemented at
the repository boundary with explicit PostgreSQL/Compose/Playwright CI gates,
upload and interaction boundary hardening, and deterministic four-viewport
browser coverage. Stage 13A has activated the isolated staging stack through
the repository rollout state machine: staging-only storage, OAuth, email/DNS,
GitHub Environment, TLS, Basic Auth, server, runtime, immutable images,
recovery backup, public smoke, and schema-3 attestation boundaries have passed.
The owner explicitly accepted retiring the partially working legacy
application; its preserved containers remain stopped while the new shared edge
owns ports 80/443. Live content/browser acceptance and the staging
backup/restore drill have also passed. Milestone 12A / Stage 14A part 1 is now
implemented and accepted on staging as release
`c9e9cf76db1c5e36601717a528d5b8d2a237a097`: the first public-UI visual
foundation, route-specific Bridge footer remediation, immutable images,
release manifest, schema-3 attestation, and live browser QA passed on top of
the accepted functional contracts. Stage 14B is implemented and accepted on
staging as release `5dfd2d17d52972a188cd9d156d219fe229bfbb1a`: it repairs
the shared mobile shell, simplifies the header, Feed, and icon-only Bridge, and
adds one private bounded Feed reaction batch read without changing the publicly
cached post list. Required CI, immutable images, the ordinary staging rollout,
schema-3 attestation, and read-only live Chrome QA passed. Stage 16 is also
accepted on staging as release
`43f5a05213f13d7c5129ddebd05955fc3186de82`: the explicit custom reaction
catalog, two-phase legacy-safe migration, immutable asset sync, picker/API/UI,
and Search/Bridge polish passed required CI and live QA. New-stack production
deployment, production provider configuration, DNS changes, data migration,
and promotion remain out of scope and unverified.

## Stage 15 editorial workflow and archive publications

Stage 15 is implemented at the repository boundary from exact parent
`1224339994df3371c4eeb47a7ad7ad7d5dc2e278`; final CI, staging rollout, and
live acceptance evidence will be appended after those gates complete. The
pre-change active staging application release was
`43f5a05213f13d7c5129ddebd05955fc3186de82`, and `origin/main` remained
`1d02912430277cdf5465f856b158a6820bc12be4`.

The CMS remains entirely Wagtail-owned. Supported Wagtail 7.4 edit handlers,
panels, page forms, admin URL/menu/dashboard/CSS hooks, and StreamField chooser
metadata provide:

- a permission-aware `New post` action that dynamically resolves the single
  valid `BlogIndexPage` and fails closed for a missing, ambiguous, misplaced,
  or unauthorized parent;
- a writing-first **Write / Publish / SEO & sharing** editor with title,
  excerpt, and wide body flow first, clear archive/newsletter intent, secondary
  tags and sharing fields, and unchanged Wagtail revision, preview, scheduling,
  privacy, unpublish, history, and rollback controls;
- chooser descriptions and Text, Media, Lists, Code / Data, and Structure
  grouping for all 13 stable body block IDs without changing stored StreamField
  JSON;
- scoped semantic-variable CSS with responsive desktop layouts, visible focus,
  reduced-motion handling, and no Django Admin override or fragile DOM patch.

`BlogPostPage.original_published_at` is nullable revision content. The API adds
nullable `original_published_at` and `display_published_at` while
`published_at` and `updated_at` retain their Wagtail meanings. Display time is
`original_published_at or first_published_at`; Feed ordering is descending
display time with descending page ID as the stable tie. Feed cards, post
`<time>`, headless/backend preview, and Open Graph use that display time.
Visibility, schedules, expiry, email cutoff, outbox availability, and
revalidation timestamps continue to use actual Wagtail/application time.
Search keeps relevance first and Wagtail's safe descending-ID tie.

The revision checkbox **Notify subscribers on first publication** defaults on.
`PostPublicationEmailDecision` stores a constrained durable
`pending → queued|suppressed` result outside revisions. The decision path locks
the post and decision rows in one transaction, rechecks canonical public
visibility, and either links exactly one existing-contract publication outbox
event or records suppression with no outbox/delivery/provider I/O. Future and
restricted posts wait until they are actually public; direct privacy removal
also covers restricted descendants. Republish, slug change, edit, and restored
revisions cannot change a final result.

The additive data migration backfills an existing publication event as queued,
an ever-published post without one as suppressed, and never-published drafts or
not-yet-public schedules as pending. Its forward/reverse test preserves
historical outbox/delivery/provider IDs and snapshots and creates no email
work. Live staging counts will be recorded from the rollout migration output.
ADR 0007 and `docs/editorial-workflow.md` contain the durable contract and the
owner workflow.

Local verification before the feature commit passed:

- exact `uv 0.11.32` lock check, Ruff format/lint, Django system and production
  deploy checks, migration drift, a clean empty-SQLite migration chain, the
  populated forward/reverse Stage 15 migration test, and the full SQLite suite
  (`546 passed`, `9` PostgreSQL-only tests deselected);
- Prettier, ESLint, TypeScript, all `178` Vitest cases, the production Next
  build, runtime-origin verification, browser asset scanning, and `npm audit`
  with zero vulnerabilities; package manifests and the lockfile did not
  change, so local `npm ci` was intentionally not repeated;
- all `45` browser-contract cases across the required public viewports and
  themes, plus all `7` real-Django cross-stack cases, including the Wagtail
  dashboard/editor flow at `768×1024`, `1440×900`, and `1920×1080`, explicit
  dark preference, keyboard focus, reduced motion, axe, overflow, preview,
  scheduling controls, archive publication, and durable no-email suppression;
- shell syntax, Python compilation, artifact sanitization, and all `229`
  infrastructure unit tests.

Docker and a local PostgreSQL server are not installed on this workstation.
The required CI `backend-postgresql` job therefore remains the authoritative
no-skip PostgreSQL search/order/concurrency and full-suite run, while the
required infrastructure job remains authoritative for Compose, Nginx, image,
container, backup/recovery, and egress checks.

## Stage 16 custom reaction catalog

Stage 16 was delivered before Stage 15 through the planned two-release
expand/activate rollout and accepted on staging on 2026-07-30. Stage 15 now
follows it; Stage 17 remains untouched.

The owner approved all 228 supplied files for controlled staging evaluation,
with no catalog exclusions and quick IDs `pepeclap`, `pepehmm`, and
`pepelove`. Because the corpus has no source, author, attribution, or license
material, every item remains `staging-only/unverified`; search-engine
availability and noncommercial use are not treated as a production rights
basis. There is no active new-stack production deployment or production
catalog/data. The production check is a future fail-closed safety contract,
not a statement that production currently exists.

The expansion release marker
`2d3c04faa08835e2b1d8cadb4eb1649870633f17` deployed commit
`61112e61e0d0a88ed9125bc441ec4e06a516289a` through CI/deploy run
`30564257262`. Operation
`deploy-30564257262-staging-2d3c04faa08835e2b1d8cadb4eb1649870633f17`
applied additive migration `discussions.0003_reaction_catalog_expansion`,
preserved all Unicode rows/columns, and activated the manifest/Wagtail/import
architecture while the prior Unicode application contract remained live. Its
release-manifest JSON SHA-256 is
`62b2574db6f46c0bc8913bb7c5b384769d4b071395cf3355e0bb46b44f51708c`
and staging-attestation JSON SHA-256 is
`083355eaf4824d3f95887f9c1df4ac0391ef41e4b70b2d9373513ccdbe4b28e7`.

The explicit manifest is `stage16-staging-v1`, SHA-256
`1b0a409b80ddb46eed4059a19210eec82f5444530eb268a33d5cb0945e08c018`.
Two local prepare runs were byte-identical and produced the same 228-item /
276-object attestation JSON SHA-256
`c9b1eaee39db47dc4725aaa5604e873a9fad154f95ba4b45bdb468bc54c16914`.
The allowlist contains 180 static and 48 animated items. Detected source
formats were 128 PNG, 52 WebP despite `.png` names, and 48 GIF. The largest
normalized object is 200,832 bytes, below the fixed 512 KiB limit. Real source
and normalized binaries were never added to Git, browser bundles, or images.

Bounded encrypted sync run `30588326706` completed verification, upload,
activation, and an idempotent repeat under operation
`catalog-sync-30588326706-staging-2d3c04faa08835e2b1d8cadb4eb1649870633f17`.
Catalog attestation artifact `8777666567` has JSON SHA-256
`ca6452ef8a0bb995cdb21ab7771484a6677cec9ba5955913fff3d0c921d94a61`.
It verified 228 rows and 276 immutable objects under `staging/media`, with
`created=0` during upload, `created=228` during activation, and
`created=0, updated=0` during the idempotent repeat. Database counts changed
from `0 catalog / 2 legacy post / 0 legacy comment` to
`228 catalog / 2 legacy post / 0 legacy comment`; the historical Unicode rows
remain intact and hidden from the new contract. The worker was restored
healthy by the bounded cleanup trap. The public encrypted prerelease/tag,
asset, one-use Environment secret, transfer variables, key, plaintext archive,
and ciphertext were deleted after attestation. Catalog sync and both deploy
gates are `false`.

Activation release `9c2f6d4e6e1ae39cd1dbf72e7affc55b9c50dd03` applied
`discussions.0004_activate_catalog_reaction_identity` through run
`30589404234`, operation
`deploy-30589404234-staging-9c2f6d4e6e1ae39cd1dbf72e7affc55b9c50dd03`.
The migration makes legacy uniqueness partial on non-empty Unicode values,
retains the legacy columns and rows, keeps custom `PROTECT` uniqueness/indexes,
and supports populated `0004 → 0003 → 0004` tests without destroying either
identity. The API accepts only `{"reaction_id":"<catalog-id>"}`, returns
catalog descriptors and catalog-ID participant paths, and omits disabled and
unmapped legacy rows.

Live QA found and fixed three client defects: the picker initially assigned
all 228 poster sources despite `loading=lazy`, accessibility text could append
“reaction” twice, and a participant dialog could remain stale after a
mutation. Fix commit `c249666eb0f51ca186e2359bd60d12f3a8059c5b` passed full
required CI run `30591122641`. Final rollout marker
`43f5a05213f13d7c5129ddebd05955fc3186de82` deployed it through run
`30591503850`, operation
`deploy-30591503850-staging-43f5a05213f13d7c5129ddebd05955fc3186de82`.
The rollout created backup
`/srv/kirillwynn/backups/staging/20260730T235218Z_9c2f6d4e6e1ae39cd1dbf72e7affc55b9c50dd03_pre-migration_deploy-30591503850-staging-43f5a05213f13d7c5129ddebd05955fc3186de82.dump`;
there were no new migrations after already-applied `0004`.

Final release artifact `8778617590` has GitHub archive digest
`sha256:a0fab4ad988eb68d19800c30df1c954fde5a34ec3714bd7b550e4e5b4141f343`
and release-manifest JSON SHA-256
`1bc7a1350cf231a7d01d1742dd30aca82666f8e61fb7d23b941e35070f03f316`.
Staging attestation artifact `8778654379` has archive digest
`sha256:ec57e1a2889ba40f5decc5d9977d71de259d7a7ea4e7acb9d595cf70f910587a`
and JSON SHA-256
`45657ec2ec8d07830f6f80a68f69f3b0aaf24ae98998c17f5afe7535373b0b82`.
All seven attestation checks passed. Active image digests are Django
`sha256:8953a6a6851f5eeacfb4863da55826beb6d37d724160159ef02a09999b410eee`,
Next
`sha256:3e318976ab28c65684188e999dc5c1080add0be67cd38bbd9b9fcb3f796e09eb`,
and edge
`sha256:3e90e20fe656ab613dbf5cc118487f794e83b9ba5de6bc39de9270a47c96b1f0`.

Verification passed:

- `uv 0.11.32 lock --check`, Ruff format/lint, Django checks, migration drift,
  521 SQLite tests with seven PostgreSQL-only tests deselected, mandatory
  PostgreSQL migration/concurrency coverage, 27 focused catalog tests, and the
  229-test infrastructure/container/MinIO suite;
- `npm ci`, Prettier, ESLint, TypeScript, 176 Vitest tests, production Next
  build, standalone runtime-origin verification, browser secret/storage-key
  scans, lazy-chunk inspection, and `npm audit` with zero vulnerabilities;
- five real-Django cross-stack tests and 45 browser-contract tests across
  320×812, 375×812, 768×1024, 1440×900, and 1920×1080, including both themes,
  axe, keyboard/touch/Escape/focus restoration, Search/Bridge polish, reduced
  motion, overflow, hydration, and console boundaries;
- live authenticated Chrome QA for static and animated reactions in post,
  comment/thread duplicate instances, Feed, participants, and picker. The
  picker exposes 228 buttons but initially creates only 50 visible images,
  requests no GIF until an animated result receives keyboard focus, and then
  requests exactly one. Escape restores focus, offscreen animation uses the
  poster, controlled mutations were removed afterward, and no console or
  hydration errors remained;
- live Search and Bridge checks in both themes found no focus/hover outline,
  ring, shadow, or border recoloring while preserving a perceptible surface
  change. Reaction buttons remain 44×44 px;
- sampled static WebP, animated GIF, and poster objects returned exact MIME,
  `public, max-age=31536000, immutable`, catalog/version/hash metadata, and
  bytes matching SHA-256
  `f47ae26cbae8833345a59b8fa848bac75420a3e3ba9f78fde5640968974b52d9`,
  `604f8ccd2ac6dd164adf48245e1e31dc929ef0e3d29083f8561a5403739c11fc`,
  and
  `7a0c548502d98dd97b644088d17f6bb82956869a47f531fa6b6b0e526072066f`.

Stage 16 is complete for staging. A future production promotion remains
prohibited until a separately reviewed `production-approved` manifest records
an acceptable rights basis for every item. Removing the legacy columns,
archiving unmapped Unicode rows, or collecting old immutable objects remains a
separate contract/cleanup scope. No production, `main`, DNS, OAuth/Resend
provider, or legacy-data state was changed.

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

## Stage 13A staging activation

Repository and GitHub verification completed on 2026-07-28:

- Baseline `d6e166d865b0e4d8159ac5d8ee97a3c960ef479e` on
  `rewrite/wagtail-next` matched the requested parent and began from a clean
  worktree. The first activated release was
  `c59a8c007cd52bf7b538e3a793f6233612c6bbfb`; the functionally accepted
  staging release is `a519284551f62258d67fe546801ca01fdc484e2c`. No history
  was rewritten or squashed.
- Draft PR #32 targets `main`; no history was rewritten or squashed.
- GitHub Environment `staging` allows only `main` and
  `rewrite/wagtail-next`. Repository-level server credentials are inherited;
  unique environment-level application, PostgreSQL, signing, Basic Auth, S3,
  OAuth, Resend, webhook, and strict host-key boundaries are present. Secret
  names were checked without reading or logging values.
- Staging uses a private, versioned Timeweb S3 bucket, dedicated access
  identity, `staging/media` prefix, and separate CDN origin with a 1 GiB
  monthly traffic cap and notifications. No production bucket, prefix, or
  credentials were reused.
- Separate Google and GitHub OAuth applications use only the exact staging
  callbacks. Resend uses the verified `mail.staging.kirillwynn.com` sender,
  staging-only sending key/idempotency namespace, exact signed webhook, and
  delivered/bounced/complained events. SPF, DKIM, and monitored DMARC
  (`p=none`, aggregate reports to the controlled owner mailbox) resolve in
  public DNS.
- Push CI run `30406997473` attempt 1 passed `backend-sqlite`,
  `backend-postgresql`, `frontend`, `browser-contract`, `cross-stack`,
  `infrastructure`, `ci-required`, immutable image builds, release-manifest,
  server preflight, and real secret/variable runtime rendering. Deployment
  remained disabled for that attempt. Attempt 2 was deliberately canceled
  before release-image jobs after detecting that a full rerun would violate
  the build-once activation boundary.
- Push CI runs `30408290526` and `30408776933` passed every required
  repository gate, three immutable image builds, release-manifest creation,
  and server preflight. Their staging deploy jobs failed before creation of a
  rollout operation: first because edge bootstrap did not bind the manifest
  digest before Compose inspection, then because the legacy Nginx already
  owned ports 80/443. Neither failure reached backup, database bootstrap,
  migration, application startup, public smoke, or attestation.
- CI-discovered repository defects were fixed in separate commits: Wagtail
  test bootstrap/locale handling, subscription locking/timestamps and
  PostgreSQL row locks, Gunicorn module launch, HTTPS internal probes,
  integration MinIO credentials, bounded failure diagnostics, existing VPS
  secret mapping, public-origin preservation for internal content requests,
  bounded internal Django hosts, retained Playwright report formats, shared
  edge security headers, rebuild-branch staging release invocation, ephemeral
  GHCR authentication, TLS/Basic Auth host preflight, real runtime rendering
  before activation, provider-assigned bucket names with strict staging
  prefixes, and first-use shared-edge bootstrap under the release lock.
  Stage 13A additionally fixed manifest edge-digest binding (`ba99ccf`) and
  added fail-closed foreign-ingress detection before any edge mutation
  (`78eb114`); the full local infrastructure suite passes 219 tests.
- After the owner-approved legacy retirement freed host ports 80/443, push CI
  run `30409906601` for `2acb088` passed `backend-postgresql`,
  `backend-sqlite`, `frontend`, `browser-contract`, `cross-stack`,
  `infrastructure`, `ci-required`, all three immutable image builds,
  release-manifest generation, real-secret runtime rendering, and the updated
  server preflight. Deployment remained disabled for this preflight run.
  `STAGING_DEPLOY_ENABLED` was then enabled for one fresh build-and-deploy
  candidate; no earlier build is being rerun.
- Fresh activation run `30410853672` for `96307f2` passed `ci-required`,
  all three immutable image builds, manifest generation, runtime rendering,
  and server preflight. Operation
  `deploy-30410853672-staging-96307f2043d57dbc8f7fb4a7728bacfb027d0d65`
  durably bootstrapped the new staging PostgreSQL volume, took and verified
  the one `initial-empty` backup, applied all migrations, and passed
  PostgreSQL, Django, worker, Next, internal readiness, worker heartbeat and
  egress, exact-image, and candidate `nginx -t` gates. Public smoke then
  failed with HTTP 500 before finalize or attestation.
- Bounded shared-edge logs identified the failure: Docker had created
  `/etc/nginx/.htpasswd` as a directory during the earlier interrupted
  bootstrap, while preflight's `install` and `test -s` incorrectly accepted
  the directory. Nginx therefore failed to read the Basic Auth file before
  proxying `/api/health/`. The failed operation and its database/backup
  evidence remain authoritative; no volume, database, or rollout state was
  deleted or edited.
- The invalid directory, containing only the generated staging auth file, was
  moved intact to
  `/srv/kirillwynn/evidence/staging-htpasswd-directory-30410853672`; the same
  credential was installed as a regular file without exposing it.
  Commits `b0e3e77`, `8076dc5`, and `81083ee` add fail-closed regular-file
  gates, controlled same-digest edge remounting, and an explicit
  GitHub-Environment-backed reviewed retry/fix-forward transport. Local infra
  verification passes 221 tests. Push runs `30411672690`, `30427213423`, and
  `30427640990` each passed the relevant CI/build/server-preflight gates with
  activation disabled.
- GitHub Environment staging is now temporarily armed with the exact failed
  operation pointer and `fix-forward` resolution kind. The next fresh push
  candidate must build once, claim that failure through
  `begin-resolution`, take a recovery backup of the existing staging
  database, repair/re-attest the shared edge, pass public smoke, and finalize
  before activation is disabled again.
- Reviewed fix-forward run `30428026501` for `16bda3f` claimed the first
  failure under operation
  `fix-forward-30428026501-staging-16bda3f8b6afc9d0eace182cebfa307f3848d6b6`,
  took and verified recovery backup
  `20260729T063021Z_96307f2043d57dbc8f7fb4a7728bacfb027d0d65_recovery_fix-forward-30428026501-staging-16bda3f8b6afc9d0eace182cebfa307f3848d6b6.dump`,
  found no new migrations, re-attested the application, and force-recreated
  the edge with a regular auth mount. Public smoke still returned HTTP 500:
  the regular file was `0600 root:root`, so the pinned Nginx worker
  (`uid=101`, `gid=101`) could not read it.
- Commit `1995b70` changes the least-privilege contract to `root:101 0640` and
  executes candidate and active readability gates as `101:101`. Local infra
  verification remains 221 passing tests. Push run `30429128197` passed the
  complete CI/build/server-preflight path with activation disabled, including
  installation of the corrected host permissions and a worker-readable
  candidate mount.
- Reviewed fix-forward run `30429525445` for `c59a8c0` claimed the second
  failure under operation
  `fix-forward-30429525445-staging-c59a8c007cd52bf7b538e3a793f6233612c6bbfb`,
  took and verified recovery backup
  `20260729T065923Z_16bda3f8b6afc9d0eace182cebfa307f3848d6b6_recovery_fix-forward-30429525445-staging-c59a8c007cd52bf7b538e3a793f6233612c6bbfb.dump`,
  found no new migrations, passed Django/Next/worker readiness, worker
  heartbeat and egress, exact-image, candidate and active `nginx -t`, and
  authenticated public smoke, then finalized the rollout and emitted a
  schema-3 staging attestation with every required check true. The reviewed
  resolution variables were removed and `STAGING_DEPLOY_ENABLED` was returned
  to `false`.
- Live Draft Mode acceptance exposed one repository defect: relative Wagtail
  preview redirects were being resolved against the internal Django service
  origin. Commit `a519284551f62258d67fe546801ca01fdc484e2c` preserves the
  public request origin for Draft Mode entry and exit redirects and adds
  regression coverage. Push run `30433997967` attempt 2 passed
  `backend-sqlite`, `backend-postgresql`, `frontend`, `infrastructure`,
  `browser-contract`, `cross-stack`, `ci-required`, all three immutable image
  builds, server preflight, manifest, deployment, and attestation. Operation
  `deploy-30433997967-staging-a519284551f62258d67fe546801ca01fdc484e2c`
  completed through the repository state machine, and
  `STAGING_DEPLOY_ENABLED` was disabled again.

Actual staging verification completed:

- Compose 2.34.0, GHCR authentication, durable restricted directories,
  staging TLS, ACME webroot, generated htpasswd, and edge runtime contract
  passed the initial server checks. Before the first activation attempt the
  staging PostgreSQL volume and rollout state were absent; the first state
  machine operation then created them durably, and both reviewed fix-forwards
  reused them without deletion or manual state edits.
- The preserved legacy `nginx` and `app` containers remain `Exited (0)`. The
  new shared edge owns ports 80/443, and
  `https://staging.kirillwynn.com` presents valid TLS and requires Basic Auth.
  The documented unauthenticated exclusions remain reachable: an absent ACME
  challenge returns 404 and an unsigned Resend webhook request returns 400,
  while the site root returns 401 without credentials.
- Immutable active images are Django
  `sha256:2ace8750ed59c3216f6b4f82429e777da0bee5e8b56fda9b1c4298822ca79823`,
  Next
  `sha256:6daad2bb9b15b12d2d04a5dc45b546a0b5ed147a1b9cfd9cc4e2a05cffeb23b7`,
  and edge
  `sha256:9557b326814d9bb908464f4835d4ebc977956bfed271bd762a9d31a1110fad4b`.
- `STAGING_DEPLOY_ENABLED` was enabled only after all preceding server,
  runtime, provider, storage, OAuth, email, TLS, DNS, free-port, and
  fail-closed ingress and auth-mount preflight checks passed. It was disabled
  immediately after the successful reviewed resolution.
- Wagtail authoring passed with a Unicode-slug post containing all 13
  StreamField blocks, JPEG/PNG/WebP media served through the staging S3/CDN
  boundary, tags, SEO metadata, an OG image, draft revision, preview, publish,
  and revision rollback. Scheduled publish and scheduled unpublish both
  changed public visibility through the staging worker and delivered signed
  revalidation events.
- Feed, search, tag filtering, pagination, the Unicode post, Bridge and all
  eight external links, and the anonymous reader boundary passed. Separate
  Google and GitHub consent/login callbacks and logout passed with minimal
  identity scopes.
- Comments, replies, edit/delete tombstones, the full-screen mobile thread,
  post reactions, picker search, and participant attribution passed.
  Subscription double opt-in, the real confirmation message, publication
  email, unsubscribe, and signed Resend `email.delivered` webhook events with
  HTTP 200 passed. Basic Auth continued to protect ordinary staging pages;
  ACME and the signed webhook remained the documented unauthenticated
  exceptions.
- Draft Mode remained isolated from public content and cache revalidation
  followed publish/schedule changes. Keyboard skip navigation, visible focus,
  Escape dismissal, and horizontal-overflow checks passed at 375x812,
  768x1024, 1440x900, and 1920x1080. The same release also passed the
  mandatory 20-case Playwright browser-contract matrix in CI.
- Manual staging backup
  `20260729T091251Z_a519284551f62258d67fe546801ca01fdc484e2c_manual_stage13a-drill-20260729.dump`
  has schema-2 staging metadata and SHA-256
  `e67de74d60d5928053259ea359ffb8786acc832dd0867353b528c88533a4ca3a`.
  The repository scripts verified the checksum and `pg_restore --list`, then
  restored only into `restore_stage13a_20260729_0913`. The restored database
  had no pending migrations, passed `check --deploy`, and matched the active
  database for the sampled Page/BlogPostPage/Subscriber/Comment counts
  (`17/14/1/2`). It did not replace or become the configured staging database.
- Repository verification and actual staging verification are complete for
  Stage 13A. Production deployment, production DNS, OAuth, Resend, S3,
  database migration, smoke tests, and promotion remain explicitly open.
- The ingress decision was resolved by migrating the only host ingress from
  the legacy production Nginx to the shared edge. On 2026-07-28 the owner
  explicitly decided that preserving legacy uptime is unnecessary and
  accepted its retirement risk. The legacy `nginx` and `app` containers were
  stopped cleanly and retained in `Exited (0)` state; they, their mounts, and
  their data were not deleted. Ports 80/443 were confirmed free. Stage 13A
  still does not renew the production certificate, deploy the new production
  application, alter production DNS/providers/storage/database, or promote a
  release to production.

## Milestone 12A / Stage 14A visual foundation

The first visual-design slice was implemented and deployed to staging on
2026-07-29:

- Baseline `2c25f48498d0286632ae6707f45c28d75cf17cf8` on
  `rewrite/wagtail-next` matched the requested parent and began from a clean
  worktree. The repository instructions, architecture/ADR boundaries,
  implementation status, and private Obsidian product note were reconciled
  before editing.
- The selected direction combines a warm, minimal reading canvas with the
  graphite, gray, and orange signal language of LeetCode's authenticated
  problem-solving interface. The Feed uses the compact information rhythm of a
  Slack news channel without a separate topical label; tags carry the topic.
  Post titles remain deliberately restrained as an experiment rather than a
  card headline.
- One semantic token system now owns typography, color, spacing, radii,
  borders, shadows, focus, and motion. The responsive shell, skip navigation,
  header/navigation, footer, Feed controls, message-like post entries,
  pagination, subscription placement, Bridge, and shared loading/empty/error/
  not-found/Draft Mode states use that foundation.
- Light and dark themes are mandatory public-site variants. The first visit
  follows `prefers-color-scheme`; a manual light/dark choice persists in
  localStorage across routes and reloads. A small pre-paint initializer in the
  document head prevents a wrong-theme flash, while the hydration-stable
  semantic icon button remains immediately beside the Login/account slot in
  either auth state. Both palettes cover all existing public surfaces without
  a new dependency and inherit the reduced-motion contract.
- `Current Team — Yandex` and `Previous Team — Deeplay` were removed from the
  Bridge main content. Only `/bridge` adds them to the footer as semantic
  definition-list content with subdued typography; its copyright and the
  former tagline are absent. Feed, post, login/account, subscription, service
  states, and every other route retain the ordinary copyright footer without
  team history.
- A global Draft Mode banner keeps an exit available on Feed and
  preview-unavailable/not-found states. Existing content, REST, cache,
  OAuth/session, CSRF, subscription, comment/reaction, and lazy Emoji Mart
  contracts remain unchanged, and no runtime dependency was added.
- Detailed restyling of the 13 post blocks, comments/threads, reaction picker
  and participants, login/account, and subscription flow is intentionally
  deferred to subsequent visual slices. Wagtail Admin remains a separate
  editorial interface.
- Visual commit `60f4f02ff64c446223497f2c9334bc906bc284be` was preserved
  without amend or history rewriting. Remediation commit
  `14c5458c6368902ef67690c509240539ed6ca4d2` isolated the exact Bridge footer
  contract. Push CI run `30470270475` attempt 1 failed before any staging
  mutation because Linux font metrics exposed a mobile-header overflow; fix
  commit `c9e9cf76db1c5e36601717a528d5b8d2a237a097` corrected the constrained
  mobile account slot without changing desktop layout.
- Push CI run `30471177757` attempt 1 passed every required repository job,
  three immutable image builds, server preflight, release manifest,
  deployment, and schema-3 attestation. Ordinary operation
  `deploy-30471177757-staging-c9e9cf76db1c5e36601717a528d5b8d2a237a097`
  completed successfully. `STAGING_DEPLOY_ENABLED` was immediately returned
  to `false`; resolution variables remained empty/absent.
- Active images are Django
  `sha256:19e96cc33ed27990d2ffef74d10fb6c8154613bd2bfb2411e0772b39fd9e6dd9`,
  Next
  `sha256:a84de51f9b6b26e72d60560d21bd49f899255103d557c402301c693367be6504`,
  and edge
  `sha256:0c78fadaf1fa5fb8f54fddd126d3ab9c951f6c13a73d9d027f12f1ffd4c828df`.
  The release-manifest artifact passed with ZIP digest
  `sha256:bd48e6847620344d7302be2965be8fb921e2875bf80689275895111572cf68a3`;
  the schema-3 staging attestation passed every required check with ZIP digest
  `sha256:372f00cfec5b3bf353d517a9801ad9097b7bf518187d57abcf1ca61057d5ae09`.
- Production, `main`, PR merge, production DNS/providers/storage/database,
  secrets, and preserved legacy containers, mounts, and data were not changed.

## Stage 14B mobile shell and Feed reaction remediation

Stage 14B is implemented and accepted on staging on 2026-07-29:

- The shared `.site-container` contract now owns actual inline bounds for
  header, main, and footer. It preserves the existing desktop maximum, gives
  mobile content at least 16 CSS pixels on each side, increases the normal
  gutter from 640px upward, and accounts for left/right safe-area insets
  without globally masking horizontal overflow. Feed, Bridge, post,
  login/account, subscription credential routes, preview, loading,
  error/invalid, and not-found states inherit the same axis.
- The visible `kirillwynn.com` header brand/link is removed. Feed remains the
  home link; Feed, Bridge, theme, and login/account controls preserve
  `aria-current`, keyboard focus, 44px touch targets, and a non-overflowing
  320px layout.
- Normal Feed and loading states retain one visually hidden `h1` named
  `Feed`; the visible heading above search/tags is removed. Invalid URLs keep
  their own visible `h1`, while empty and filtered states remain subordinate
  to the Feed heading. Metadata and Open Graph contracts are unchanged.
- Bridge is deliberately icon-only. Its main content has one visually hidden
  `h1` named `Bridge`, no description, and no visible social-network labels.
  Each of the eight external links has one unique accessible name while its
  decorative SVG is hidden from assistive technology. The links retain
  `_blank`, `noopener noreferrer`, keyboard focus, at least 44x44 targets, and
  centered icons in both themes and every required viewport. No label appears
  after image loading, hover, focus, theme changes, or responsive changes.
- The Bridge-only semantic `dl` footer now lays out `Current Team — Yandex`
  and `Previous Team — Deeplay` as two vertical rows. Bridge still omits its
  copyright and former tagline; every ordinary route retains only the normal
  copyright without team history.
- `GET /api/v1/reactions/posts/?ids=...` is a separate private/no-store
  `SessionAuthentication` read with anonymous access. It accepts exactly one
  strict list of at most 50 unique positive IDs, applies the canonical public
  post visibility policy, safely omits unknown/non-public IDs, preserves
  requested order, emits Unicode-safe participant URLs, and loads selection,
  aggregate counts, and viewer state in bounded grouped queries. The publicly
  cacheable post-list representation remains viewer-independent.
- Next adds only the exact same-origin batch rewrite. Feed issues one request
  for its current page and progressively adds compact existing reaction pills
  below excerpts. The pills reuse shared mutation ownership and participant
  accessibility, show count/viewer state, and deliberately omit quick
  reactions, the add button, and Emoji Mart. Empty aggregates take no space;
  one failed batch leaves all cards usable without repeated errors. Draft Mode
  does not start the private hydration request.
- The API contract and ADR 0003 record the batch parsing, visibility, query,
  session, cache, and exact-rewrite decisions. No model or migration changed,
  and the existing single-post aggregate/toggle/participant endpoints remain
  unchanged.

Local verification passed before commit:

- `uv lock --check` resolved 74 packages. Ruff format checked 144 files; Ruff
  lint, Django test-settings check, migration drift, an empty in-memory SQLite
  migration chain, and the production deploy-check passed.
- The SQLite CI selection passed 516 tests with seven PostgreSQL-only cases
  deselected. Docker, PostgreSQL, `psql`, `postgres`, and `pg_isready` are not
  installed locally; the seven PostgreSQL locking/search/concurrency cases and
  PostgreSQL migration execution remain mandatory fail-on-skip CI work and are
  not represented by SQLite.
- Prettier, ESLint, TypeScript, and full Vitest passed: 164 tests in 18 files.
  The Next.js 16.2.11 production build, staging/production runtime-origin
  verifier, browser-static-asset secret/internal-origin scan, and
  `npm audit --audit-level=high` passed with zero vulnerabilities.
- Playwright cross-stack passed 5/5 against real Django views, SQLite sessions,
  standard CSRF, exact Next rewrites, and persistence, including real Feed
  batch hydration. Browser-contract passed 32/32 across 375x812, 768x1024,
  1440x900, and 1920x1080, plus a separate 320px header assertion. It covers
  both themes, persistence, reduced motion, axe, hydration/console diagnostics,
  keyboard/focus, exact content bounds, horizontal overflow, icon-only Bridge
  aria snapshots, centered icons, footer rows, Feed batch failure/empty state,
  participant access, and absence of Feed picker/quick controls.
- Shell parsing/compilation and all 221 deterministic infrastructure tests
  passed. Local Compose/Nginx/image/container rehearsal remains unavailable
  because Docker is absent and is not represented as passed.

CI, deployment, and live acceptance passed:

- Feature commit `39b1b20d45f9179afa9cacc60e46de8bd98d15c8` has exact
  parent `ce6c5b9e786f013d75469caa02488ef46267b3c7`. Push CI run
  `30481008202` attempt 1 passed all required jobs, including the mandatory
  PostgreSQL suite, and produced a gate-disabled green candidate. The
  docs-only activation commit
  `5dfd2d17d52972a188cd9d156d219fe229bfbb1a` is its direct child and does
  not change the Stage 14B runtime tree.
- Fresh push CI/rollout run `30481995267` attempt 1 passed backend SQLite and
  PostgreSQL, frontend, browser-contract, cross-stack, infrastructure,
  `ci-required`, three immutable image builds, server preflight, manifest,
  ordinary staging deployment, and complete attestation. The gate was enabled
  only for this fresh build-and-deploy candidate and returned to `false`
  immediately after the terminal success.
- Release-manifest artifact `8736177640` has GitHub SHA-256
  `c12669fdaaf0bbfc2b1e216be4be9185e4503539e20c44c773c450e5b6175b20`
  and independently validates for the deployed SHA. Active image digests are
  Django
  `sha256:c0cf317773a283fa9b8f606872ed875692ed463b5680acae51d9b4c75da062f9`,
  Next
  `sha256:08af73f6469282009b55fa2429474b5a29ffa1351b6bf5ffa83909863a3022fe`,
  and edge
  `sha256:8ad5da3d093bd3894a84275da8c451393cb0817b572958de4fd4971ffedaceef`.
- Ordinary operation
  `deploy-30481995267-staging-5dfd2d17d52972a188cd9d156d219fe229bfbb1a`
  took the isolated pre-migration backup
  `20260729T185946Z_c9e9cf76db1c5e36601717a528d5b8d2a237a097_pre-migration_deploy-30481995267-staging-5dfd2d17d52972a188cd9d156d219fe229bfbb1a.dump`;
  Django reported no migrations to apply. PostgreSQL, Django, worker, Next,
  exact-image, candidate/active edge configuration, worker heartbeat/egress,
  and authenticated public smoke gates passed before finalize.
- Schema-3 attestation artifact `8736318071` has GitHub SHA-256
  `9a3a775b6e25ac21dd2885600ad453088bd67cfecd6f2861cd79492ac895ddb6`,
  status `passed`, the exact release/operation/images, and every required check
  true. It independently validates against the release manifest.
- Read-only live Chrome QA passed icon-only Bridge and hydrated Feed in light
  and dark themes at 375x812, 768x1024, 1440x900, and 1920x1080, plus the
  320px header/layout check. Bridge exposed only its sr-only heading and eight
  unique link names to accessibility, kept every icon centered and loaded,
  kept 88px targets and two vertical team rows, and never rendered the
  forbidden heading, description, or network labels. Feed retained one
  sr-only `h1`, displayed the existing `Stage 13A newsletter delivery` 👍 1
  with pressed viewer state, preserved the named participant dialog and
  focus return, and rendered no picker/quick/add controls.
- Feed, Bridge, the known post, login/account, confirm/unsubscribe, empty and
  invalid Feed, and not-found routes had at least 16px mobile bounds, a shared
  header/main/footer axis, and no root horizontal overflow. `aria-current`,
  44px header targets, theme persistence, visible keyboard focus, skip-link
  focus transfer, hover/focus icon-only behavior, and zero captured
  console/hydration warnings or errors passed. Loading, preview, reduced
  motion, batch failure/empty behavior, and axe remain covered by the green
  deterministic local and CI Playwright matrix rather than inferred from a
  transient live state.
- Production, `main`, production credentials/providers/database/S3/Resend/
  OAuth/DNS, content, comments, reactions, and e-mail state were not mutated.
  The repository rollout stayed within the isolated staging projects; the
  preserved legacy containers, mounts, and data were not targeted or changed.

## Stage 14C shell, reactions, and live-search remediation

Stage 14C is implemented, deployed, and accepted on staging from
`rewrite/wagtail-next` as of 2026-07-29:

- Every public Next.js route and shared loading/error/not-found state now uses
  one centered semantic `dl` footer. Its only visible content is
  `Current Team — Yandex` and `Previous Team — Deeplay` on separate rows;
  route-specific footer branching, copyright, owner name, year, tagline, and
  all other footer text are removed. Bridge remains icon-only with its
  visually hidden `h1` and eight unique accessible link names unchanged.
- The existing Feed and Bridge links now share one compact right-aligned header
  group with theme and account/login in the exact order Feed, Bridge, Theme,
  Account/Login. Existing names, `aria-current`, focus treatment, 44px controls,
  safe-area gutters, and non-overflowing 320px behavior are preserved.
- Feed and post-detail reaction pills have a 30px visual shell, 16px emoji, and
  12px count while each separate button retains a non-overlapping 44px hit
  target. Emoji Mart cells and comment/thread picker behavior are unchanged.
- Feed participant reads are explicit-activation-only: hover, pointer entry,
  focus alone, touch followed by a synthetic mouse event, and all pre-activation
  states issue no participant request. Click/tap and native Enter/Space count
  activation open the existing responsive surface; Close, Escape, focus return,
  stale-request rejection, and participant deduplication remain intact. Post,
  comment, and thread behavior is deliberately unchanged.
- Feed search now applies URL state with an approximately 300ms debounce and
  `router.replace`. It preserves the active tag, resets pagination without
  serializing `page=1`, removes an empty `q`, encodes Unicode once, synchronizes
  back/forward state, supports immediate Search/Enter submission, suppresses
  intermediate IME navigation, cancels stale timers, and prevents duplicate or
  superseded navigation. `Clear search`, `Clear tag`, and generic
  `Clear filters` controls are removed; ordinary text deletion and `All` own
  those reset paths.
- The REST search/cache contract, database schema, Draft Mode, batched Feed
  reaction read, theme persistence, post/comment/thread APIs, and Bridge
  content contract did not change.

Local verification passed before the feature commit:

- `uv lock --check` resolved 74 packages. Ruff format checked 144 files; Ruff
  lint, Django test-settings check, migration drift, an empty SQLite migration
  chain, and the production deploy-check passed. The SQLite CI selection passed
  516 tests with seven PostgreSQL-only cases deselected.
- Prettier, ESLint, TypeScript, and full Vitest passed: 169 tests in 18 files.
  The Next.js 16.2.11 production build, runtime-origin verifier, browser-static
  secret/internal-origin scan, retained Playwright artifact scans, and
  `npm audit --audit-level=high` passed with zero vulnerabilities.
- Browser-contract passed 32/32 across 375x812, 768x1024, 1440x900, and
  1920x1080, plus the dedicated 320px assertions. Coverage includes both
  themes, axe, visible focus, hydration/console diagnostics, horizontal
  overflow, universal footer routes/states, icon-only Bridge, reaction geometry
  and touch targets, explicit Feed participant activation, Unicode/debounced/
  IME/back-forward search, Draft Mode, theme persistence, and batched Feed
  reactions. Cross-stack passed 5/5 against real Django views, SQLite sessions,
  standard CSRF, exact Next rewrites, and persistence.
- Shell parsing/compilation and all 221 deterministic infrastructure tests
  passed. Docker, Compose, Nginx, PostgreSQL, `psql`, `postgres`, and
  `pg_isready` are unavailable locally, so local container and PostgreSQL
  execution are not claimed; both remained mandatory in CI.

Commit, CI, deployment, and acceptance evidence:

- Feature commit `776ffa80f1f99851078a844bf0da9aa878c53476` has exact
  parent `5ad3f51547e6aa46a31bb374e2c1454b827965d2`. Push CI run
  `30491324455` attempt 1 passed backend SQLite and PostgreSQL, frontend,
  browser-contract, cross-stack, infrastructure, `ci-required`, all three
  immutable image builds, server preflight, release-manifest creation, and the
  gate-disabled staging job.
- Release artifact `8739942335` has GitHub SHA-256
  `752e0cfd216192b432ed06cad5e56bad58c50599d8a95fccac4ed358e9c9a156`.
  `STAGING_DEPLOY_ENABLED` remained `false` for that run, so it performed no
  activation.
- Docs-only activation candidate
  `3e6b7a46c0ffacdde4bb47d61c942f1142c9e379` has exact parent
  `776ffa80f1f99851078a844bf0da9aa878c53476` and an unchanged runtime tree.
  With the staging gate temporarily enabled, fresh CI run `30491882619`
  attempt 1 passed backend SQLite and PostgreSQL, frontend, browser-contract,
  cross-stack, infrastructure with Docker/Compose/Nginx/container smoke,
  `ci-required`, all three immutable image builds, server preflight, manifest,
  ordinary staging deployment, and complete schema-3 attestation.
- The accepted operation is
  `deploy-30491882619-staging-3e6b7a46c0ffacdde4bb47d61c942f1142c9e379`.
  The pre-migration backup is
  `/srv/kirillwynn/backups/staging/20260729T212530Z_5dfd2d17d52972a188cd9d156d219fe229bfbb1a_pre-migration_deploy-30491882619-staging-3e6b7a46c0ffacdde4bb47d61c942f1142c9e379.dump`;
  Django reported no migrations to apply.
- The active immutable images are Django
  `sha256:b66e6f1807905027603035935e99ddd3da0976a32d74031938b3cfa52a10fdc9`,
  Next
  `sha256:bc5512f1112c22f1e2ffe05e7ae6aef351825422c9e942e55b5750a473b4ac9d`,
  and edge
  `sha256:373d9fad09c7cf3d1fb7f66e4996271a5a8865733a2cdf9e1e5aa1cf66c1f22e`.
  The attestation passed active-digest, Django readiness, Next health, edge
  candidate config, public smoke, worker egress, and worker heartbeat checks.
- Manifest artifact `8740149221` has GitHub and independently computed
  SHA-256
  `ccfc504cf9a8634341ee62e8ab53315d4fe7028297fb4ebddbb123ff57d6e83e`.
  Attestation artifact `8740325012` has GitHub and independently computed
  SHA-256
  `a854d9e2ea22d88b7639adf7674c3800f190951e4181f404d4728832186541ce`.
  Both downloaded JSON files passed the repository manifest/attestation
  validators against the exact release SHA and each other.
- Read-only live Chrome acceptance passed Feed, known post, Bridge,
  login/account, confirm/unsubscribe, not-found, ordinary no-results,
  unknown-tag, and invalid-parameter states. The two semantic centered footer
  rows were the only visible footer content on desktop and 320px; Bridge kept
  its hidden `h1`, eight icon-only links, and eight unique accessible names.
  The right header order, `aria-current`, 44px targets, safe gutters, keyboard
  order, 3px visible focus, skip-link transfer, and zero root overflow passed
  at 320, 375x812, 768x1024, 1440x900, and 1920x1080.
- Live Feed and post pills measured 30px visually with a 16px emoji, 12px
  count, and adjacent non-overlapping 44px button targets. Feed hover and
  focus alone opened no dialog; click, Enter, and Space opened the named
  surface, while Escape and Close restored count focus. Desktop rendered the
  320px anchored popup and 320px rendered the full-width fixed drawer.
- Live search preserved tag, removed page, encoded `日本` once, cleared `q`
  through ordinary keyboard deletion, applied Enter/Search immediately, and
  synchronized the input through back/forward. Deterministic CI coverage
  remains the source of truth for exact debounce/request counts, IME event
  synthesis, stale timers, loading/error injection, Draft Mode, axe, and
  batch-reaction request cardinality.
- Light/dark persistence, the live DOM asset/secret/internal-origin scan, and
  console/hydration inspection passed; no warning or error was captured.
  Live acceptance created no content, comment, reaction, subscription, or
  email mutation. The theme was restored to light and the temporary viewport
  override was removed.
- `STAGING_DEPLOY_ENABLED` was returned to `false` at
  `2026-07-29T21:31:51Z`. `origin/main` remained
  `1d02912430277cdf5465f856b158a6820bc12be4`; production, production
  providers/database/S3/Resend/OAuth/DNS, preserved legacy containers,
  mounts/data, and application data were not targeted or changed.

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
- [x] Stage 14A part 1 establishes shared visual tokens, responsive shell,
  mandatory light/dark themes, navigation/footer, compact Feed, Bridge, and
  their shared UI states.
- [x] Theme selection follows the first-visit system preference, persists only
  after a manual choice, initializes before paint without a hydration mismatch,
  and remains keyboard-accessible beside anonymous and authenticated controls.
- [x] Bridge team history moved out of main content into a semantic,
  route-specific footer that is regression-tested against ordinary routes.

## Milestone transition

Milestone 11, functional Stage 13A acceptance, Stages 14A–14C, and Stage 16
staging acceptance are complete. Stage 15 is implemented and moving through
its final verification and staging-only acceptance sequence. The pre-Stage-15
active staging release is
`43f5a05213f13d7c5129ddebd05955fc3186de82`.

### Next recommended session

After Stage 15 acceptance, perform the separately scoped small Stage 16
remediation: remove the three suggested/quick reactions and retain one picker
button. Then proceed to Stage 17. Do not combine either task with Stage 15.

### Exit criteria

- Stage 15 required CI and mandatory PostgreSQL coverage pass.
- A checked staging PostgreSQL backup precedes the migration.
- The immutable staging-only rollout and schema-3 attestation pass with both
  staging gates restored to false.
- Controlled no-notification CMS QA proves archive dates, preview, publication,
  revisions, cache movement, and durable suppression without changing real
  user posts or provider state.

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
- [x] Functional staging acceptance and launch.
- [ ] Milestone 12 — visual design and polish.
  - [x] Stage 14A part 1 — tokens, light/dark themes, shell, Feed, Bridge, and
    shared states.
  - [x] Stage 14B — mobile shell/gutters, simplified header/Feed/icon-only
    Bridge, Bridge footer rows, and Feed post reaction hydration; accepted on
    staging.
  - [ ] Stage 15 — implementation complete; CI/staging acceptance in progress.
  - [x] Stage 16 — custom static/animated reaction catalog accepted on staging.
  - [ ] Stage 16 remediation — remove three suggested reactions and retain one
    picker button; explicitly outside Stage 15.
  - [ ] Stage 17 — begin only after the separate Stage 16 remediation.

## Known risks

- Stage 14B is accepted only on staging as
  `5dfd2d17d52972a188cd9d156d219fe229bfbb1a`; no production result is
  implied.
- Feed reaction hydration is intentionally progressive: one failed private
  batch read leaves the public post cards usable and emits no repeated
  card-level error, so aggregate state can be temporarily absent during a
  reaction-service failure.
- Detailed post blocks, comments/threads, reaction/participant surfaces,
  login/account, and the subscription flow intentionally retain their prior
  structure until later visual slices; shared tokens affect their base colors
  but do not constitute detailed redesign acceptance.
- Feed titles are a deliberately restrained experiment. The owner may remove
  them after judging real content density against the intended Slack-channel
  rhythm.
- The Next.js duplicate-event registry is process-local. Duplicate invalidation
  remains safe across processes because tag/path invalidation is idempotent.
- Preview snapshot and delivered revalidation event retention are currently
  bounded only by opportunistic preview cleanup and database operations; a
  formal operations retention command belongs with worker infrastructure.
- The bounded worker runtime passed Docker/PostgreSQL staging heartbeat,
  egress, scheduling, and email-delivery checks. Operational alerting and
  retention policy remain future operations work.
- Staging S3 media, CDN origin, versioning, lifecycle, CORS, and the isolated
  prefix passed live checks. Production object storage remains unconfigured.
- Separate staging OAuth applications and live Google/GitHub consent passed.
  Production applications, credentials, callbacks, and smoke tests remain
  unconfigured and must not reuse the staging boundary.
- Docker build, Docker Compose config, and PostgreSQL-backed migrations remain
  unverified locally because Docker and PostgreSQL server binaries are not
  available. YAML parsing and route-contract tests are not represented as
  Docker Compose, image, Nginx, PostgreSQL, or integration-runtime verification.
- Seven PostgreSQL-only search/locking/concurrency cases were deselected from
  the local SQLite run because no PostgreSQL or container runtime is installed.
  They run in a dedicated CI selection where any skip fails the job; the
  production model was not weakened or imitated for SQLite.
- Local Chromium passed the complete deterministic Playwright matrix at all
  four required viewports. Actual staging Chrome checks also passed live
  OAuth/Resend/S3, target Nginx, keyboard interaction, mobile threads, and the
  four viewports. Neither result verifies production.
- Legacy migrations contain resets and multiple heads and should not be reused
  as the new baseline.
- The shared edge cannot be replaced independently per application environment;
  a changed edge digest requires a production-approved host-wide operation
  compatible with both live application versions.
- A server carrying superseded multi-file
  `active-release.json`/manifest/pending state or schema-2
  `rollout-state.json` must not be auto-adopted. The schema-3 loader fails
  closed and requires a reviewed one-time migration before any rollout.
- Staging email DNS, verified Resend sender, webhook registration, credentials,
  and GitHub Environment activation are configured and accepted. Equivalent
  production boundaries remain deliberately unconfigured.
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

2026-07-29:

- Stage 14C began from clean exact local/origin parent
  `5ad3f51547e6aa46a31bb374e2c1454b827965d2` on
  `rewrite/wagtail-next`; active staging was
  `5dfd2d17d52972a188cd9d156d219fe229bfbb1a`, `origin/main` was
  `1d02912430277cdf5465f856b158a6820bc12be4`, and the deployment gate was
  false. Repository instructions, product/architecture/status/API/deployment
  sources, relevant ADRs, and the private Obsidian specification were read
  before editing; no history was rewritten.
- Feature commit `776ffa80f1f99851078a844bf0da9aa878c53476`
  (parent `5ad3f51547e6aa46a31bb374e2c1454b827965d2`) and docs-only activation
  candidate `3e6b7a46c0ffacdde4bb47d61c942f1142c9e379`
  (parent `776ffa80f1f99851078a844bf0da9aa878c53476`) are intact. Gate-disabled
  candidate run `30491324455` and controlled rollout run `30491882619`, both
  attempt 1, passed the complete required matrix without a fix commit.
- Staging operation
  `deploy-30491882619-staging-3e6b7a46c0ffacdde4bb47d61c942f1142c9e379`,
  schema-3 attestation, independently verified manifest/attestation artifacts,
  exact active digests, pre-migration backup, and read-only live Chrome
  acceptance all passed. The active staging release is
  `3e6b7a46c0ffacdde4bb47d61c942f1142c9e379`, and the gate is back to
  `false`; exact evidence is recorded in the dedicated Stage 14C section.

- Stage 14B began from clean exact local/origin parent
  `ce6c5b9e786f013d75469caa02488ef46267b3c7` on
  `rewrite/wagtail-next`; active staging remained
  `c9e9cf76db1c5e36601717a528d5b8d2a237a097`, `origin/main` remained
  `1d02912430277cdf5465f856b158a6820bc12be4`, and the deployment gate was
  false. Repository instructions, architecture/status/testing/deployment
  documents, relevant ADRs, and the private Obsidian product source were read
  before editing.
- The owner's corrected Bridge contract superseded the initial Stage 14B
  wording before any commit or external mutation. The final candidate is an
  icon-only eight-link grid with a visually hidden heading and unique
  accessible link names; it contains no visible heading, description, or
  network labels.
- Stage 14B feature commit
  `39b1b20d45f9179afa9cacc60e46de8bd98d15c8` has exact parent
  `ce6c5b9e786f013d75469caa02488ef46267b3c7`. Push CI run `30481008202`
  attempt 1 passed backend SQLite and PostgreSQL, frontend,
  browser-contract, cross-stack, infrastructure, `ci-required`, all three
  immutable image builds, release-manifest creation, server preflight, and the
  gate-disabled staging job. Its release artifact is `8735803770`; no
  activation occurred because `STAGING_DEPLOY_ENABLED` remained false for the
  run.
- Stage 14B local verification is recorded in its dedicated section above.
  Docs-only direct child `5dfd2d17d52972a188cd9d156d219fe229bfbb1a`
  triggered fresh run `30481995267` attempt 1 after the gate was enabled.
  Required CI, immutable builds, server preflight, manifest, ordinary operation
  `deploy-30481995267-staging-5dfd2d17d52972a188cd9d156d219fe229bfbb1a`,
  schema-3 attestation, and read-only live Chrome acceptance all passed. The
  active staging release is `5dfd2d17d52972a188cd9d156d219fe229bfbb1a`
  and the gate is back to `false`; exact image/artifact evidence is recorded in
  the dedicated Stage 14B section.

Earlier Stage 14A acceptance on the same date:

- Baseline branch, exact parent
  `2c25f48498d0286632ae6707f45c28d75cf17cf8`, clean starting worktree,
  repository instructions, architecture/ADR boundaries, implementation status,
  and the private Obsidian note were verified before editing. No history was
  rewritten.
- Commit `60f4f02ff64c446223497f2c9334bc906bc284be` remained intact.
  Bridge footer remediation was committed separately as
  `14c5458c6368902ef67690c509240539ed6ca4d2`; the CI-discovered mobile-header
  correction was committed separately as
  `c9e9cf76db1c5e36601717a528d5b8d2a237a097`.
- Push CI run `30470270475` attempt 1 failed before mutation on two 375px
  browser overflow assertions. Push CI run `30471177757` attempt 1 for
  `c9e9cf76db1c5e36601717a528d5b8d2a237a097` then passed
  `backend-sqlite`, `backend-postgresql`, `frontend`, `infrastructure`,
  `browser-contract`, `cross-stack`, `ci-required`, all three immutable image
  builds, release manifest, server preflight, staging deployment, and schema-3
  attestation without a rerun or manual deploy.
- Before code changes, read-only Chrome QA audited the accepted live staging
  release across Feed search/tag/pagination/empty/error states, Bridge, post
  and all 13 blocks, login/account, subscription, comments/mobile and desktop
  threads, reactions/participants/picker, loading/error/not-found, and Draft
  Mode at 375x812, 768x1024, 1440x900, and 1920x1080. No real content or
  account data was mutated.
- After implementation, Chrome visually checked the local light Feed and
  Bridge on desktop. Local Playwright screenshots inspected the dark Feed at
  375x812, 768x1024, 1440x900, and 1920x1080, the light Feed at 375x812 and
  1440x900, and dark Bridge and post/comments at 375x812 and 1440x900. This
  found and corrected light-canvas contrast defects in three legacy social
  SVGs and a transient mobile auth-placeholder header wrap. The development
  indicator visible over some screenshot corners is absent from production.
- `npm run format:check`, `npm run lint`, and `npm run typecheck` passed.
  Full Vitest passed 159 tests in 17 files. `npm ci` was not rerun because
  neither dependency manifest nor lockfile changed and the installed lock was
  exercised by every frontend command.
- The Next.js 16.2.11 production build passed. Standalone servers resolved both
  staging and production public origins at runtime, and the post-build
  `.next/static` scan found no internal mock/Django origin, sensitive
  credential names, or `X-Session-Token`.
- Playwright browser-contract passed 28/28: seven flows at each of 375x812,
  768x1024, 1440x900, and 1920x1080. The light matrix and the mandatory dark
  surface loop include axe, skip-link focus, keyboard interaction, no
  horizontal overflow, route-specific footer isolation, Draft Mode isolation,
  a globally available exit from an unavailable preview, auth safety,
  comments/threads/reactions, and subscription confirmation/unsubscribe.
  Theme coverage verifies dark and light first-visit system preferences,
  pre-body initialization, no hydration diagnostics, 44px keyboard activation,
  reduced motion, manual persistence across route/reload and later system
  changes, and stable placement beside both Login and an authenticated account.
  The first expanded run also found the standalone invalid-Feed state lacked an
  `h1`; the semantic heading was corrected before the final passing matrix.
- The existing cross-stack suite passed 4/4 during this session against real
  Django API views, SQLite sessions, standard CSRF, Next rewrites, and
  persistence; the Django system check also passed. Later edits were limited to
  public presentation, client-only theme selection, semantic headings, and
  browser assertions, with no API or backend integration change, so those two
  integration checks were not rerun after the final frontend-only changes.
- After deployment, live Chrome QA passed Feed, search, tags, pagination,
  Bridge, an ordinary post, light/dark switching and persistence, desktop and
  375x812 mobile layouts, keyboard/focus behavior, footer isolation, hydration
  and console diagnostics, horizontal overflow, and DOM internal-origin/secret
  scans. Bridge main omits team history; its semantic footer contains only
  `Current Team — Yandex` and `Previous Team — Deeplay`, with no copyright or
  former tagline. Ordinary routes retain only the approved copyright footer.
  First-visit system preference could not be independently repeated in the
  already-persisted live Chrome profile; it passed the local and CI Playwright
  matrix at all four viewports.
- Server state after rollout is schema 3 with no in-progress or recovery
  operation. The active sequence is `30471177757`, the active operation is
  `deploy-30471177757-staging-c9e9cf76db1c5e36601717a528d5b8d2a237a097`,
  and Django, Next, worker, PostgreSQL, and shared edge are healthy. The legacy
  `nginx` and `app` containers remain preserved in `Exited (0)` state.
- `STAGING_DEPLOY_ENABLED` was false after rollout. Production, `main`, PR,
  production DNS, OAuth, Resend, S3, database, secrets, and legacy
  containers/mounts/data were not changed. Real provider and email mutations
  were intentionally not repeated for this presentation-only slice.

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
