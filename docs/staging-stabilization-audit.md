# Stage 18 staging stabilization audit

Last updated: 2026-08-01

Status: in progress. Local deterministic verification is complete for the
implementation candidate, but required GitHub CI, the controlled staging
rollout, the fresh backup/isolated-restore drill, automated five-viewport live
acceptance, and final gate restoration evidence are still pending. This file
must not describe Stage 18 as complete until all of those boundaries pass.

## Scope and baseline

Stage 18 is a post-MVP stabilization audit and staging release-candidate
exercise. It is not a new product milestone and does not authorize production.
No production Environment, Compose project, database, volume, bucket/prefix,
DNS, TLS, OAuth, Resend configuration, secret namespace, release, promotion,
or workflow state may be created or changed.

The independently verified pre-mutation baseline was:

- clean local and origin `rewrite/wagtail-next` at docs-only SHA
  `ac0a7cd1cc5c386e9b9a74e299ea51d8cd3e792f`;
- unchanged `origin/main` at
  `1d02912430277cdf5465f856b158a6820bc12be4`;
- active staging application release
  `ebb02aae0cf463f430e9906d9d8c77e8e782379e`, not the docs-only branch tip;
- active rollout operation
  `deploy-30720283303-staging-ebb02aae0cf463f430e9906d9d8c77e8e782379e`;
- Django image
  `sha256:e7b6c9fb29dc222ebb954e1e78e9eb101de33bbb2bc5299077e15c83ba205088`
  and Next image
  `sha256:1cf17b1eea3cf1c0d05808424f9ccfb6ab4668b6e430a36d7f76834cd4de55b5`;
- candidate edge image
  `sha256:36b0aee56079970f9bde4053377500794a2c3029011eb64998ccf1db84a29e24`.
  It was attested but correctly did not replace the older active shared Edge
  merely because it was newer;
- release artifact `8824718001`: archive SHA-256
  `c61e13d155eb9e4fb1c6f8c92237dc000a526ff5a29ea05a3fe5da3cdd3e409c`
  and manifest JSON SHA-256
  `68e5d02cf0a255912ddd4a14c08617b6bf4b6a7ecbea8af0e64c7e4a550e0e5e`;
- schema-3 attestation artifact `8824741742`: archive SHA-256
  `518fdbb017b2d82b9766fe638e80d8a0e0c2e4f7cb5b24de50ee35a64c1d45e3`
  and JSON SHA-256
  `aad8147bea9563b8ceb9a3b68da0cef70f68888a5c54a8eb17950c6ce0c5f27a`.
  All recorded readiness, Next health, worker heartbeat/egress, edge-candidate,
  active-image, and public-smoke checks were true;
- successful branch CI run `30722568373` and PR CI run `30722569763` for the
  docs-only tip. Deployment and attestation were skipped with the gate closed;
- staging Environment and repository `STAGING_DEPLOY_ENABLED=false`, staging
  catalog sync false, and no one-shot operator/recovery variables;
- no exact GitHub Environment named `production`; the legacy `kw_prod` and
  `kw_staging` names were not changed;
- no production rollout state, production Compose containers, database/cache
  volumes, or environment-qualified networks on the server. Preserved legacy
  containers, mounts, and data were not touched.

No baseline discrepancy was found. The active shared Edge identity will be
recorded from the authoritative schema-3 state in the fresh audit evidence.

## Issue matrix

| Finding | Severity | Evidence | Disposition |
| --- | --- | --- | --- |
| Footer rendered an em dash instead of the exact two-line `Current Team:` / `Previous Team:` contract | P2 | Real staging browser plus computed `dt::after` content | Fixed locally with the one-character CSS correction and browser regression coverage. |
| Anonymous Login retained a stale `next` value after Feed live-search replaced the query string | P2 | Real staging browser reproduced `/` after the visible URL became `/?q=...` | Fixed by deriving the target from pathname plus reactive search parameters; unit and browser regressions cover Unicode live search. |
| Node 20 action releases were being forced onto Node 24 by GitHub Actions | P2 maintenance | Existing workflow warnings and upstream action manifests/releases | Updated to reviewed Node 24-compatible upstream releases pinned to full immutable SHAs. Permissions, provenance, sanitization, and gates are unchanged. |
| The first draft of the new audit workflow held the rollout concurrency lock per job | P2 tooling | Static review showed a possible rollout window between recovery and browser jobs | Corrected before first use by holding the shared release-operation lock for the entire workflow; regression guard added. |
| A discarded password from a failed pre-remediation signup attempt exists in an internal local automation transcript | P2 local data hygiene | Exact-value, project-scoped fail-closed scan found only two mirrored internal Codex transcript records and no Git/worktree/GitHub artifact/release-bundle occurrence | The value is not an active credential and is never reproduced. The internal transcript store is not safely mutable through the project workspace, so it was not edited or deleted. Application/DB/browser evidence is rechecked without exposing the value. |
| Rollback-only quick-reaction schema and internal config endpoint remain | P3 backlog | `ReactionSettings` keeps three Unicode fields, three catalog FKs, and Django `/api/v1/reactions/config/`; the frontend and its exact proxy allowlist do not consume or expose that route | Retain during the rollback window. Remove only after previous-release compatibility is retired, with a backward-compatible migration and cache plan. |
| Custom emoji rights remain unverified | Production blocker | All 228 items are expected to remain `staging-only/unverified` | Deliberately unchanged. No production approval exists. |

## Remediation contracts

The frontend fixes are deliberately local. Neither changes an API, schema,
catalog item, stored user/content row, authentication architecture, or visible
design beyond restoring the already documented text and navigation contracts.
The regression surface includes the unit auth header, deterministic
five-viewport browser contract, and read-only live staging suite.

The maintenance update uses these official upstream releases and immutable
commit pins:

| Action | Release | Commit |
| --- | --- | --- |
| `actions/checkout` | [v7.0.1](https://github.com/actions/checkout/releases/tag/v7.0.1) | `3d3c42e5aac5ba805825da76410c181273ba90b1` |
| `actions/setup-node` | [v7.0.0](https://github.com/actions/setup-node/releases/tag/v7.0.0) | `820762786026740c76f36085b0efc47a31fe5020` |
| `actions/setup-python` | [v7.0.0](https://github.com/actions/setup-python/releases/tag/v7.0.0) | `5fda3b95a4ea91299a34e894583c3862153e4b97` |
| `actions/upload-artifact` | [v7.0.1](https://github.com/actions/upload-artifact/releases/tag/v7.0.1) | `043fb46d1a93c77aae656e7c1c64a875d1fc6a0a` |
| `actions/download-artifact` | [v8.0.1](https://github.com/actions/download-artifact/releases/tag/v8.0.1) | `3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c` |
| `docker/setup-buildx-action` | [v4.2.0](https://github.com/docker/setup-buildx-action/releases/tag/v4.2.0) | `bb05f3f5519dd87d3ba754cc423b652a5edd6d2c` |
| `docker/build-push-action` | [v7.3.0](https://github.com/docker/build-push-action/releases/tag/v7.3.0) | `53b7df96c91f9c12dcc8a07bcb9ccacbed38856a` |
| `docker/login-action` | [v4.6.0](https://github.com/docker/login-action/releases/tag/v4.6.0) | `dbcb813823bdd20940b903addbd779551569679f` |

The new manual staging-only workflow binds an operator-supplied expected active
application SHA to authoritative rollout state, verifies immutable application
and shared-Edge references, checks committed/active Compose and runtime
contracts, records health and production absence, creates a verified
custom-format backup, restores only into a new `restore_stage18_*` database,
runs migration/check/data/query-count probes there, compares PII-free active
before/restored/active-after reports, and retains the scratch database. It
never deploys, syncs the reaction catalog, points the public application at the
restore, replaces the active database, or removes a database/volume. All
retained evidence and Playwright output are fail-closed sanitizer inputs.

## Confirmed repository and browser invariants

The deterministic local suites and initial read-only real-browser audit have
confirmed Feed search/tag/pagination/history/empty/404 behavior, absence of
Clear controls, accessible non-orange search focus, aggregate reactions and
explicit participants, post metadata and all 13 StreamField blocks, comment
threads/tombstones, one lazy reaction picker trigger, reduced-motion poster
behavior, icon-only Bridge, exact shell order, theme persistence, auth and
subscription entry UI, exact route allowlists, private personalized API cache
headers, and zero browser-stored auth/session/access tokens. The controlled
browser audit did not submit auth, OAuth, subscription, comment, reaction, or
CMS mutations and did not alter the owner account or existing data.

Local verification passed:

- uv lock check, Ruff format/lint for the backend, Django system and migration
  checks, production deploy check, 715 SQLite tests with the 14 PostgreSQL-only
  cases honestly deselected;
- clean `npm ci`, Prettier, ESLint, TypeScript, 198 Vitest tests in 19 files,
  production Next build, standalone runtime-origin probes, browser-bundle
  secret/internal-origin scan, `npm audit` with zero vulnerabilities, 70/70
  deterministic browser-contract cases across the five required viewports,
  and 8/8 real-Django cross-stack cases;
- 241 infrastructure tests, shell syntax, Python compile and Ruff lint, plus
  targeted Stage 18 recovery/workflow regression tests.

Docker, PostgreSQL, `psql`, and Nginx are unavailable locally. Compose/Nginx,
container smoke, PostgreSQL-only no-skip concurrency/search, worker egress,
and the fresh recovery drill are therefore not represented as locally passed;
they remain mandatory CI/live gates.

## Performance baseline

The repository probes collect three samples and the median for Feed page 1/2,
Unicode search, tag filter/catalog, detail, comments, and batch reactions on
the isolated restored PostgreSQL snapshot. The live five-viewport suite records
initial Next static asset count/transfer/encoded bytes, layout shift,
`/api/me/` count, catalog request/image counts after picker open, responsive
image metadata, media cache/content type, and three-sample public API medians.
Exact numbers remain pending the controlled workflow artifact and will replace
this paragraph before Stage 18 completion. No broad or score-driven
optimization is authorized.

## Security and transcript audit

Existing deterministic suites cover CSRF across auth/comments/reactions/
subscriptions, hostile Origin/Referer and cross-session tokens, safe return-to,
inactive/banned/session boundaries, verified-primary-email plus confirmed
nickname interaction, OAuth/local collision and takeover protection, one-time
fragment credentials, private cache headers, absence of `SocialToken`/JWT/
Auth.js/browser tokens, exact Next/Nginx routes, response security headers,
S3 content/cache/upload contracts, and fail-closed artifact sanitization.

The pre-remediation discarded password was never accepted by signup and is not
described as a current credential. A bounded scanner compared its exact bytes
without printing them against the tracked project, all project Git objects,
project-related Codex transcripts, selected CI artifacts, and release bundles.
Only two mirrored internal transcript JSONL records matched; Git, the
worktree, CI artifacts, manifests, attestations, and release bundles did not.
The failed transactional signup path, password-hash-only data audit, browser
storage audit, and absence of an accepted account/outbox lifecycle provide the
application/DB/browser evidence without copying the value. Unknown personal
files outside project-related scope were not scanned or deleted.

## Remaining gates and production blockers

Before completion, the implementation commit must pass full push/PR CI while
deployment remains disabled. Because the CSS/Next runtime changed, one
controlled staging rollout must then pass immutable build, pre-migration
backup, migration, health, schema-3 attestation, and live acceptance. Deployment
must be returned to false, catalog sync must remain false, and one-shot values
must be absent. The fresh stabilization workflow must pass against the new
active SHA. A final documentation-only commit must pass required CI with
deployment and attestation skipped.

Production remains blocked by the absence of a production Environment and all
production infrastructure/provider configuration, by the lack of a separately
approved production rollout/promotion decision, and independently by the 228
custom emoji items whose rights are still `staging-only/unverified`.
