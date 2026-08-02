# Stage 18 staging stabilization audit

Last updated: 2026-08-01

Status: completion candidate. Local deterministic verification, closed-gate
push/PR CI, the controlled staging rollout, schema-3 attestation, gate
restoration, fresh backup/isolated restore, and automated five-viewport live
acceptance are complete. Final live workflow `30754896193` passed at exact
audit-only SHA `76478921604adb0734686b6a50e106a4f209a92f`; active staging
application release `07542f5a90d2849577219ed74a1628ba39555674` remains
unchanged. No product/runtime, catalog, user-content, account, subscription, or
mail-state mutation followed that rollout. The only remaining completion gate
is closed-gate CI for the documentation-only commit containing this report;
Stage 18 is not declared complete until that evidence passes.

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
- no production rollout state, production application Compose containers,
  database/cache volumes, or production database/application/egress networks
  on the server. Per ADR 0005, the pre-existing shared Edge project owns both
  environment-qualified edge networks even while production is absent.
  Preserved legacy containers, mounts, and data were not touched.

No application-release discrepancy was found. Later fail-closed recovery
evidence corrected one baseline wording error: the dormant production-edge
network is shared-Edge infrastructure, not a production application stack.
Because staging deliberately does not own an Edge snapshot in schema 3, the
fresh audit reads the running shared-Edge digest directly and binds it to
matching immutable durable release manifests.

## Issue matrix

| Finding                                                                                                                                           | Severity               | Evidence                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 | Disposition                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| ------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Schema-3 rollout state creation used the Python 3.11-only `datetime.UTC` alias on the Python 3.10 VPS host                                        | P1 operational         | Attempt 2 of run `30727380396`, deploy job `91444944090`, failed in `record_rollout_state.py:now()` before `begin` wrote the operation; the log recorded `shared_edge=existing`, the public footer remained the prior release, and attestation upload was skipped                                                                                                                                                                                                                                                                                                                                                                                                        | Replaced the alias with `datetime.timezone.utc`. A regression simulates a host datetime module without `UTC`; closed-gate CI, the full 242-test infrastructure suite, a direct system-Python compatibility probe, and the later successful rollout all pass.                                                                                                                                                                                                                                                                                           |
| The first recovery-audit reader required `active.edge` in staging even though schema 3 deliberately keeps Edge production-owned                   | P2 tooling             | Audit run `30730318625`, recovery job `91449388175`, rejected the otherwise valid staging snapshot before backup; the deployment runbook and state-machine code both require staging snapshots to carry `edge=null`                                                                                                                                                                                                                                                                                                                                                                                                                                                      | The reader now requires the documented null staging field, independently reads the live shared-Edge digest, binds it to immutable durable manifests, verifies the running Edge before and after the drill, and has regression coverage. No backup, restore, or data change occurred in the rejected run.                                                                                                                                                                                                                                               |
| Live shared-Edge discovery invoked Compose before `EDGE_IMAGE` was known                                                                          | P2 tooling             | Audit run `30730968704`, recovery job `91451228121`, failed on the compose file's required image interpolation before an evidence directory or backup existed                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            | Discover the existing container through its exact Compose project/service labels, then read `.Config.Image`, bind the digest to immutable manifests, and let the normal active-Edge verifier export the matched digest. Static regression coverage prevents reintroducing the circular Compose lookup. No backup, restore, or data change occurred.                                                                                                                                                                                                    |
| The production-absence probe treated the shared Edge project's dormant production-edge network as a production application object                 | P2 tooling             | Sanitized audit artifact `8831902252` from run `30742919327` proves active application/runtime/Edge health and no Compose drift, then job `91483433251` stops at the generic production-object check before backup. ADR 0005 and the committed Edge Compose contract require the shared project to own both edge networks before either application exists                                                                                                                                                                                                                                                                                                               | Keep production rollout state, application containers, volumes, and database/application/egress networks forbidden. Require the exact production-edge network to be Compose-owned by `kirillwynn-edge` and attached only to the unchanged active Edge container. Add static regression coverage and clarify the recovery runbook. No backup, restore, or data change occurred.                                                                                                                                                                         |
| The recovery wrapper lost bounded phase evidence when a child exited under `set -e`                                                               | P2 tooling             | Both recovery executions of run `30743388424` (jobs `91484692581` and `91485010762`) passed release/runtime/production checks, wrote byte-identical `data-active-before.json`, then ended with status 1 before `backup-metadata.json`. At the time their sanitized artifacts could not distinguish a failing data audit from a backup failure                                                                                                                                                                                                                                                                                                                            | Persist a fixed, non-secret phase ledger from the start of the audit and classify dump/list child exit statuses, empty dumps, and missing dump/metadata paths explicitly. Run `30744256944` then placed the failure before `active-data-before-read`, proving that neither the earlier retry nor the new run reached backup. This does not change backup format, destination, retention, restore target, or database data.                                                                                                                             |
| The read-only data audit used a mistyped catalog digest and allowed Django shell auto-import text before JSON                                     | P2 tooling             | Run `30744256944`, recovery job `91487034152`, passed release/runtime/production boundaries. Sanitized artifact `8832340568` (archive SHA-256 `26f3f4069254793b9c28b2de783739738b0fba4a19e8095f3610abe909f6c0d6`) stops at `production-boundary-verified`; its data output reports 228 enabled/selectable items, 48 animated items, all 228 rights statuses unchanged, and only the false hardcoded manifest comparison as a violation. The committed manifest independently hashes to `1b0a409b80ddb46eed4059a19210eec82f5444530eb268a33d5cb0945e08c018`, while the reader constant contained a different digest                                                        | Bind the reader to the exact committed manifest digest and run all four stdin-driven audit shells with `--no-imports`. A regression computes the committed manifest hash rather than duplicating it in the test, and another requires every audit shell invocation to suppress automatic imports. The phase ledger proves no backup or restore began in this run; no catalog row, manifest, object, ordering, ID, rights status, or user data changed.                                                                                                 |
| The first complete live suite encoded three incorrect harness assumptions                                                                         | P2 tooling             | Run `30744775286`, browser job `91490560698`, and sanitized artifact `8832804364` failed identically on all five viewports: an icon-only Theme control was read through `innerText`, live Unicode input raced React hydration, and Feed participant activation was asserted on post detail                                                                                                                                                                                                                                                                                                                                                                               | Wait for the completed same-origin `/api/me/` request before client interaction, check DOM control order by accessible semantics, and assert participant click/Enter/Space plus hover/focus non-activation on Feed. Deterministic regression guards and the 70-case browser contract cover the adjacent behavior.                                                                                                                                                                                                                                      |
| The live performance probe could silently miss lead-image renditions and report reaction icons as responsive content                              | P2 tooling             | Artifact `8832804364` contained `media_headers=null`; its `responsive_images` entries were only 16px reaction icons without `sizes`/`srcset`. Real Chrome independently showed the Unicode staging fixture's 480/960/1440 `srcset`, `sizes`, intrinsic dimensions, and lazy image                                                                                                                                                                                                                                                                                                                                                                                        | Require the Unicode fixture's lead image, HEAD all three rendition URLs, assert image content type plus one-year immutable caching, navigate to that Feed result, and require `sizes`, `srcset`, and non-zero natural/rendered dimensions. Static regression coverage prevents the probe from becoming optional again.                                                                                                                                                                                                                                 |
| Restored-data inspection materialized complete Wagtail page bodies and related media on the constrained VPS                                       | P2 tooling/operational | Run `30746538731`, recovery job `91492992353`, exited `137` only when starting the restored data audit. Sanitized artifact `8833206074` (archive SHA-256 `cf574694190557e3e828f5d9f437b1d1091a3b5cb0e905cf2879a156fff44cc1`) proves the fresh backup, `pg_restore --list`, scratch restore, migration plan, and both Django checks passed first; the active release/data hashes remained identical to the successful drill                                                                                                                                                                                                                                               | Clear public-content prefetches/select-related defaults and project only post ID plus the three author fields the integrity report actually reads. Add explicit restored data/performance start/verified phases and regressions for the bounded projection. The later complete drill passed; the failed scratch database and backup remain retained per runbook.                                                                                                                                                                                       |
| Restored performance fixture discovery materialized complete Wagtail page bodies and related media                                                | P2 tooling/operational | Run `30749330524`, recovery job `91500428944`, passed release/runtime/production checks, created and verified the backup, listed/restored it, passed restored migrations/checks and the newly bounded data audit, then exited `137` at `restored-performance-audit-started` with an empty performance JSON. Sanitized artifact `8834414848` (archive SHA-256 `09b5e89ac7a000e3d8d226f769015945f5de2cf75a20abb798ff73b3cf403350`) records byte-identical active/restored data SHA-256 `2a01810aa2c54e9f090e2eb1ba111f6c777d2aae1f3c00e0d57da56974af2c37` and unchanged pre-audit release-state SHA-256 `7cfeea338ce651b4922bbbb963e08986a5b9f052d3261d0d3353dc7c8f5756b4` | Clear select/prefetch defaults and project only the ten `pk`/`slug` pairs the probe uses; resolve the optional tag directly through `BlogPostTag`. Static regression, an evaluated migrated-SQLite projection check, targeted tests, and the full 245-test infrastructure suite pass. The failed scratch database and backup remain retained per runbook.                                                                                                                                                                                              |
| Recovery audit did not reserve memory for transient Django checks on the 1 GB staging host                                                        | P2 tooling/operational | Server preflight job `91506047033` recorded 980,408 KiB total and only 55,592 KiB available. After the bounded performance fix, run `30751508059`, job `91506260468`, completed release/runtime/production checks, backup/list/restore, then exited `137` before the first restored `showmigrations` output. Sanitized artifact `8834714453` (archive SHA-256 `11aa93aaf00dc3b4db38dcdc44d951892f3346d6ace2b6badfd396c0a2c6b57f`) places the termination immediately after `scratch-database-restored`; the different kill phases across consecutive runs confirm host pressure rather than one remaining query path                                                     | Reuse the repository's small-host operational boundary: verify worker heartbeat/egress first, stop only the active worker while ephemeral Django containers run, and restore the same container through an EXIT trap. Capture bounded host/container memory and OOM counters; after the drill require worker health, heartbeat, egress, immutable release state, and Edge again. Static ordering/restoration regressions, shell syntax, targeted tests, and all 245 infrastructure tests pass. The failed scratch database and backup remain retained. |
| The final live suite treated the `.account-slot` wrapper as the Account control and treated its intentional 404-state console event as unexpected | P2 tooling             | Run `30747808973`, browser job `91498660709`, sanitized artifact `8833761029` (archive SHA-256 `6606e6081573c840cf68c7118a38c3b0397f410f725d4991841eb4bdec59078d`) reproduced both assertions on every viewport while snapshots showed the inner `Login` link and the expected 404 page                                                                                                                                                                                                                                                                                                                                                                                  | Assert the ordered fourth wrapper plus its visible accessible Login descendant, and require exactly the one Chromium resource-404 event produced by the deliberate missing-document navigation. Other console warnings/errors remain failures.                                                                                                                                                                                                                                                                                                         |
| Post-theme-reload `/api/me/` accounting raced `AuthProvider` hydration                                                                            | P2 tooling             | Run `30752529705`, browser job `91511067003`, and sanitized artifact `8835173993` (archive SHA-256 `bc4e31e291dc8d3640118e9f565053f6c9c727c21bb0384f554f34e952927996`) reproduced on every required viewport and retry: the harness observed only the pre-reload request before immediately requiring exactly two. Sixteen independent live cases passed; manual Chrome reload preserved the theme with no console log                                                                                                                                                                                                                                                   | Reuse the established hydration wait immediately after reload, then retain the exact two-request and zero-warning/error assertions. Artifact `8835449029` from the next run records exactly two requests on all five viewports, confirming this correction. A static sequencing regression, Prettier, ESLint, TypeScript, all 198 Vitest tests, and all 245 infrastructure tests pass.                                                                                                                                                                 |
| The live CLS probe generated its own Chromium deprecation warning                                                                                 | P2 tooling             | Run `30754037868`, browser job `91513524617`, and sanitized artifact `8835449029` (archive SHA-256 `fc3635fd0b358c4845afa273b2f04003512cc1f8f39c02c19c217d7a78350dcd`) reproduced only `warning:Deprecated API for given entry type.` on every viewport and retry. The probe called `performance.getEntriesByType("layout-shift")`; the same metrics record exactly two `/api/me/` requests, zero overflow, and zero axe violations                                                                                                                                                                                                                                      | Install a buffered `PerformanceObserver` for `layout-shift` before navigation/reload, retain the observer for the document, require browser support, and read the accumulated non-user-input CLS value. The zero-warning assertion is not weakened and no warning allowlist is added. Static regression forbids the deprecated call; Prettier, ESLint, TypeScript, all 198 Vitest tests, and all 245 infrastructure tests pass.                                                                                                                        |
| Footer rendered an em dash instead of the exact two-line `Current Team:` / `Previous Team:` contract                                              | P2                     | Real staging browser plus computed `dt::after` content                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   | Fixed locally with the one-character CSS correction and browser regression coverage.                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| Anonymous Login retained a stale `next` value after Feed live-search replaced the query string                                                    | P2                     | Real staging browser reproduced `/` after the visible URL became `/?q=...`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               | Fixed by deriving the target from pathname plus reactive search parameters; unit and browser regressions cover Unicode live search.                                                                                                                                                                                                                                                                                                                                                                                                                    |
| Node 20 action releases were being forced onto Node 24 by GitHub Actions                                                                          | P2 maintenance         | Existing workflow warnings and upstream action manifests/releases                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        | Updated to reviewed Node 24-compatible upstream releases pinned to full immutable SHAs. Permissions, provenance, sanitization, and gates are unchanged.                                                                                                                                                                                                                                                                                                                                                                                                |
| The first draft of the new audit workflow held the rollout concurrency lock per job                                                               | P2 tooling             | Static review showed a possible rollout window between recovery and browser jobs                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | Corrected before first use by holding the shared release-operation lock for the entire workflow; regression guard added.                                                                                                                                                                                                                                                                                                                                                                                                                               |
| The first pushed audit workflow used the step-only `runner.temp` context in job-level `env`                                                       | P2 tooling             | GitHub configuration run `30727326442` rejected the manual workflow before any job or staging action                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | Fixed additively in `aa2533a...` by scoping the path to the browser step and using the runner-provided shell variable for sanitizer input; regression guard added.                                                                                                                                                                                                                                                                                                                                                                                     |
| A discarded password from a failed pre-remediation signup attempt exists in an internal local automation transcript                               | P2 local data hygiene  | Exact-value, project-scoped fail-closed scan found only two mirrored internal Codex transcript records and no Git/worktree/GitHub artifact/release-bundle occurrence                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | The value is not an active credential and is never reproduced. The internal transcript store is not safely mutable through the project workspace, so it was not edited or deleted. Application/DB/browser evidence is rechecked without exposing the value.                                                                                                                                                                                                                                                                                            |
| Rollback-only quick-reaction schema and internal config endpoint remain                                                                           | P3 backlog             | `ReactionSettings` keeps three Unicode fields, three catalog FKs, and Django `/api/v1/reactions/config/`; the frontend and its exact proxy allowlist do not consume or expose that route                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 | Retain during the rollback window. Remove only after previous-release compatibility is retired, with a backward-compatible migration and cache plan.                                                                                                                                                                                                                                                                                                                                                                                                   |
| Custom emoji rights remain unverified                                                                                                             | Production blocker     | All 228 items are expected to remain `staging-only/unverified`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           | Deliberately unchanged. No production approval exists.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |

## Remediation contracts

The frontend fixes are deliberately local. Neither changes an API, schema,
catalog item, stored user/content row, authentication architecture, or visible
design beyond restoring the already documented text and navigation contracts.
The regression surface includes the unit auth header, deterministic
five-viewport browser contract, and read-only live staging suite.

The maintenance update uses these official upstream releases and immutable
commit pins:

| Action                       | Release                                                                     | Commit                                     |
| ---------------------------- | --------------------------------------------------------------------------- | ------------------------------------------ |
| `actions/checkout`           | [v7.0.1](https://github.com/actions/checkout/releases/tag/v7.0.1)           | `3d3c42e5aac5ba805825da76410c181273ba90b1` |
| `actions/setup-node`         | [v7.0.0](https://github.com/actions/setup-node/releases/tag/v7.0.0)         | `820762786026740c76f36085b0efc47a31fe5020` |
| `actions/setup-python`       | [v7.0.0](https://github.com/actions/setup-python/releases/tag/v7.0.0)       | `5fda3b95a4ea91299a34e894583c3862153e4b97` |
| `actions/upload-artifact`    | [v7.0.1](https://github.com/actions/upload-artifact/releases/tag/v7.0.1)    | `043fb46d1a93c77aae656e7c1c64a875d1fc6a0a` |
| `actions/download-artifact`  | [v8.0.1](https://github.com/actions/download-artifact/releases/tag/v8.0.1)  | `3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c` |
| `docker/setup-buildx-action` | [v4.2.0](https://github.com/docker/setup-buildx-action/releases/tag/v4.2.0) | `bb05f3f5519dd87d3ba754cc423b652a5edd6d2c` |
| `docker/build-push-action`   | [v7.3.0](https://github.com/docker/build-push-action/releases/tag/v7.3.0)   | `53b7df96c91f9c12dcc8a07bcb9ccacbed38856a` |
| `docker/login-action`        | [v4.6.0](https://github.com/docker/login-action/releases/tag/v4.6.0)        | `dbcb813823bdd20940b903addbd779551569679f` |

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

The additive implementation history is:

- `631e188036869ef3fce347c9ea8bbe51ab6dec78`, parent
  `ac0a7cd1cc5c386e9b9a74e299ea51d8cd3e792f`: footer and reactive auth
  return-route fixes plus regressions;
- `a8cc9e22c577330678fcd3956ff9a8cab97c80e6`, parent
  `631e188036869ef3fce347c9ea8bbe51ab6dec78`: reviewed action pins and the
  staging-only stabilization/recovery/browser audit;
- `9fb44ed38071689163a2b68c907e207fcf1efca4`, parent
  `a8cc9e22c577330678fcd3956ff9a8cab97c80e6`: initial in-progress audit
  record;
- `aa2533a9abff7c3d2ac55e953c03048339beaaec`, parent
  `9fb44ed38071689163a2b68c907e207fcf1efca4`: GitHub runner-context
  correction;
- `07542f5a90d2849577219ed74a1628ba39555674`, parent
  `aa2533a9abff7c3d2ac55e953c03048339beaaec`: VPS-host Python compatibility
  remediation and rollout evidence;
- `1f3debdde618098db348b48ac89fc4ddcb858281`, parent
  `07542f5a90d2849577219ed74a1628ba39555674`: staging/shared-Edge ownership
  correction;
- `7e5b3ff8e7fa2bd766d3c9f2648ba1006b04275d`, parent
  `1f3debdde618098db348b48ac89fc4ddcb858281`: active Edge discovery without
  circular Compose interpolation;
- `57843de5fc83cec01442c2ee8e90f4c57cd03e5e`, parent
  `7e5b3ff8e7fa2bd766d3c9f2648ba1006b04275d`: shared production-edge network
  boundary correction;
- `dd4c1a9a74ff8d1141b58b923048fedaf7c4cafa`, parent
  `57843de5fc83cec01442c2ee8e90f4c57cd03e5e`: durable audit phase/failure
  evidence;
- `cb0d2444fe038760a0ce622d75f496397fc2f356`, parent
  `dd4c1a9a74ff8d1141b58b923048fedaf7c4cafa`: catalog digest and Django shell
  output correction;
- `60c41a8e5cd2d452e51bf7883131631f5a59bb18`, parent
  `cb0d2444fe038760a0ce622d75f496397fc2f356`: live hydration, header-order,
  and Feed-participant audit alignment;
- `4ad92f96a2a82866643332cf59601131efc69a32`, parent
  `60c41a8e5cd2d452e51bf7883131631f5a59bb18`: required live responsive-media
  and CDN evidence;
- `efdaf80cf2af9f56c9b085000ec1abf7e2e55a48`, parent
  `4ad92f96a2a82866643332cf59601131efc69a32`: bounded restored-data audit
  projection and data/performance phase markers;
- `17680a1e50137b89e687eb18ff01daf376700f54`, parent
  `efdaf80cf2af9f56c9b085000ec1abf7e2e55a48`: live header-wrapper and expected
  document-404 semantics;
- `1ccb14238db396f74eb818c3ae5617fa04e2c166`, parent
  `17680a1e50137b89e687eb18ff01daf376700f54`: bounded restored-performance
  fixture projection;
- `bf28834f1b8046b84925ab423bbbc75b8a51d267`, parent
  `1ccb14238db396f74eb818c3ae5617fa04e2c166`: bounded staging-host memory
  protocol with exact worker restoration and post-audit health verification;
- `8ec34626c63f1fce6e4ce12cfd4e80386d0427a1`, parent
  `bf28834f1b8046b84925ab423bbbc75b8a51d267`: post-theme-reload hydration
  sequencing in the live audit harness;
- `76478921604adb0734686b6a50e106a4f209a92f`, parent
  `8ec34626c63f1fce6e4ce12cfd4e80386d0427a1`: warning-free buffered
  LayoutShift observer for the live CLS baseline.

No commit was amended, squashed, rebased, or force-pushed.

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
- 245 infrastructure tests, shell syntax, Python compile and Ruff lint, plus
  targeted Stage 18 recovery/workflow regression tests.

Docker, PostgreSQL, `psql`, and Nginx are unavailable locally. Compose/Nginx,
container smoke, PostgreSQL-only no-skip concurrency/search, worker egress,
and the fresh recovery drill are therefore not represented as locally passed;
they remain mandatory CI/live gates.

## Closed-gate CI evidence

Push run `30727380396` and PR run `30727381598` passed at exact head
`aa2533a9abff7c3d2ac55e953c03048339beaaec`. The push run passed SQLite
`91441507707`, PostgreSQL-only `91441507733`, frontend `91441507734`,
browser-contract `91441507750`, cross-stack `91441507720`, infrastructure
`91441507725`, and aggregate gate `91442045560`. It then passed immutable
Django/Next/Edge builds `91442053029`/`91442053008`/`91442053030`, staging
server preflight `91442053132`, and release manifest `91442262417`.

Release artifact `8826916501` has GitHub archive digest
`sha256:ae363f5a6e5613b5aacc2716edd4234b0c655fdb350a618ebfbb9f3ce385ef5c`.
The deploy job `91442277027` rendered and validated the candidate runtime but
its deploy, attestation validation, and attestation upload steps were all
skipped because `STAGING_DEPLOY_ENABLED=false`. Catalog job `91442053148` and
rollout-failure job `91442053273` were skipped. The superseded `9fb44ed...`
push/PR runs were cancelled by the documented CI concurrency after the
additive workflow correction; they are not represented as passing evidence.

Attempt 2 of the same immutable run re-executed all six required suites and
the aggregate gate successfully, skipped catalog sync, rebuilt all three image
roles, passed server preflight, and created a fresh release manifest. The
deployment then failed before the schema-3 `begin` transition because the host
Python lacks the 3.11-only `datetime.UTC` alias. No operation record, backup,
migration, application activation, attestation, or Edge replacement occurred;
the failure path therefore correctly had no operation ID to mark. The staging
Environment gate was returned to false immediately. A reloaded public Feed
still rendered the prior release's em-dash footer, independently confirming
that the candidate frontend was not activated.

The compatibility remediation then passed closed-gate push run `30728939433`
and PR run `30728940566` at exact SHA
`07542f5a90d2849577219ed74a1628ba39555674`; the closed-gate deploy job
`91446151752` skipped deployment, attestation validation, and attestation
upload, while catalog sync remained skipped. A controlled rerun passed all
required suites, builds, manifest, and preflight. Its first deploy attempt lost
SSH during `scp` before the remote rollout command; public staging briefly
returned 504, recovered on the prior release, and still showed the prior footer.
The failed-job-only retry reused the same immutable SHA, run ID, manifest, and
operation ID and completed as deploy job `91447769894`.

Active release `07542f5a90d2849577219ed74a1628ba39555674` was activated by
`deploy-30728939433-staging-07542f5a90d2849577219ed74a1628ba39555674`.
The pre-migration backup is
`20260802T025743Z_ebb02aae0cf463f430e9906d9d8c77e8e782379e_pre-migration_deploy-30728939433-staging-07542f5a90d2849577219ed74a1628ba39555674.dump`;
no migrations were pending. Pre/post checks agreed on two users, two verified
primary e-mails, two confirmed nicknames, three nickname-history rows, two
social accounts, zero social tokens, 13 public posts, zero ownerless posts,
five comments, six post reactions, zero comment reactions, and one database
session.

Release artifact `8827442606` has archive digest
`sha256:8bc8c74c85dddfa90bd31ce19e5518f8dd977666a1ae5499ac7321a67ee6cf65`
and manifest JSON SHA-256
`5069e0a9d9404a723e68e4cab74ab065e57cdd941028ea5f4b9ba2fcb425fdc6`.
The immutable images are Django
`sha256:77c6ae90b0c600dcc75bd76ef6899119f28ea194ba634d720f1c08889eaf71d2`,
Next `sha256:1a424bc98cf7d5cf647adf8a5d13fe2425f8ec5eee3c1815ae723da9b73d2186`,
and candidate Edge
`sha256:460850e0023b16a34f017a25ca1705d1ab89955a60a13053aea512389b237b7b`.
The unchanged active shared Edge is
`sha256:592d5235f8b85e16a269a922615455d4bae810168683c3f6fb242c954fb14187`,
bound to the durable `d2729bb4d5c5372053d2abb1958bfccba0663121` manifest
whose JSON SHA-256 is
`974fc6a4d629975286f8adf9a6d62600e5772807d2fabab49bac5b5cd1ea0819`.
Schema-3 attestation artifact `8827559823` has archive digest
`sha256:73b9c7e9486b3f50ce906222b329753032be7ae3c9923bcefe09d51e719a75f8`
and JSON SHA-256
`16837c35efa4d8b859af452964a42b4c32f9c23e960505a9a22edbb7a5f21e7d`.
All seven application-image, readiness, Next, worker heartbeat/egress,
edge-candidate, and public-smoke checks are true. The shared Edge was reported
as existing and was not replaced. The environment and repository deploy gates
were returned to false immediately; catalog sync remained false.

The post-rollout audit-only corrections then passed closed-gate push/PR CI at
`60c41a8...` (`30746220626` / `30746222799`), `4ad92f9...`
(`30746828014` / `30746829435`), `efdaf80...` (`30747324932` attempt 2 /
`30747326514`), `17680a1...` (`30748982596` / `30748983983`),
`1ccb142...` (`30751177980` / `30751180090`), and `bf28834...`
(`30752213992` / `30752215678`), `8ec3462...` (`30753690318` /
`30753693081`), and `7647892...` (`30754600510` / `30754602041`). The first
attempt of push run `30747324932` never started browser tests because the
official Playwright CDN returned five geographic HTTP 403 responses to that
runner; a failed/dependent-jobs-only rerun on a new runner passed without a
code change. At final audit-tooling SHA `7647892...`, all six required suites
and the aggregate gate passed, catalog sync was skipped, and deploy job
`91515162992` reported disabled activation. Its deployment, attestation
validation, and attestation upload steps were all skipped. No
post-`07542f5...` commit became an active application release.

## Recovery and data-integrity evidence

Final run `30754896193`, recovery job `91515286100`, completed the repository
runbook end to end at exact audit SHA
`76478921604adb0734686b6a50e106a4f209a92f`. Sanitized artifact `8835686488`
has GitHub archive SHA-256
`35c49f9c26391689c292b02864815d4dbd67f00a2644b1aeb2ada34da010486d`.
It records manual custom-format backup
`20260802T154501Z_07542f5a90d2849577219ed74a1628ba39555674_manual_stage18-audit-30754896193-1.dump`.
The schema-2 metadata records dump SHA-256
`a48d8844b8b856f40773c43a8b4300e53b1654115b9fd0af09354f25561c9a3c`;
the metadata JSON itself hashes to
`f5365c49d5c856b7477fb4ae9687dd6fcaa361299e36f9ba5333d55490f6492c`.
`pg_restore --list` produced a non-empty 77,684-byte listing. Restore targeted
only new database `restore_stage18_30754896193_1`; it was never attached to the
public application, did not replace staging, and remains retained with its
backup as the runbook requires.

The restored migration plan had no operations, `migrate --check`, both Django
system/deploy checks, and `makemigrations --check --dry-run` passed. The phase
ledger reached worker pause/restoration, explicit restored data/performance,
post-audit heartbeat/egress, unchanged-release-state, and `complete`. Before
the bounded worker pause, the 980,408-KiB host had 62,808 KiB available; after
pause it had 162,444 KiB, and after exact worker restoration it had 54,048 KiB.
PostgreSQL, Django, worker, and Next were healthy afterward. Active-before,
restored, and active-after PII-free reports were byte-identical at SHA-256
`2a01810aa2c54e9f090e2eb1ba111f6c777d2aae1f3c00e0d57da56974af2c37`:
43 snapshot values matched, with zero mismatches, concurrent changes, or
violation reports. Release state before/after was byte-identical at SHA-256
`7cfeea338ce651b4922bbbb963e08986a5b9f052d3261d0d3353dc7c8f5756b4`.
Compose drift output was empty; application/shared-Edge attestation and
runtime contracts passed. Production rollout state, application containers,
database/cache volumes, and database/application/egress networks were absent;
the required shared production-edge network remained owned by the shared Edge
project and attached only to the active Edge container.

The compared snapshot contains two users, two verified primary e-mails, three
nickname claims, two social accounts owned by one user, zero `SocialToken`
rows, one session, 14 posts/13 public/zero ownerless, five comments (three
roots, two replies, three deleted tombstones), six post reactions, zero
comment reactions, and two legacy Unicode post reactions. It also contains
228 enabled/selectable catalog items (48 animated, three rollback quick
relations), all with unchanged `staging-only/unverified` rights; 14 queued
publication decisions, 15 delivered publication outbox rows, two delivered
publication deliveries, two applied/two pending webhook rows, two delivered
auth outbox rows/two sent deliveries, one reset and one verification digest,
and 31 delivered revalidation rows. No pending/manual-review/processing,
stale, scheduled-due, expired-live, author-serializer, tombstone, catalog, or
credential-storage violation was reported.

## Final five-viewport live acceptance

The same run's browser job `91515937243` passed 21 cases with four intentional
non-desktop skips of the single desktop-only network baseline. Sanitized
artifact `8835715340` has GitHub archive SHA-256
`f0fd47cbda25d29de315bb8bbb49e522c2e0536a7af0ea33f29aa8b9202fbcf6`.
All five required viewports had no horizontal overflow, zero axe violations,
zero unexpected console warnings/errors, exactly two `/api/me/` requests
across the theme reload, supported buffered LayoutShift observation, one lazy
catalog request only after picker opening, and zero animated assets started
under reduced motion:

| Viewport  |     CLS | Initial Next assets | Encoded / transfer bytes | Picker DOM / loaded images |
| --------- | ------: | ------------------: | -----------------------: | -------------------------: |
| 320×812   | 0.02798 |                  10 |        169,094 / 172,094 |                     35 / 4 |
| 375×812   | 0.03232 |                  10 |        169,094 / 172,094 |                     42 / 4 |
| 768×1024  | 0.03162 |                  10 |        169,094 / 172,094 |                      7 / 4 |
| 1440×900  | 0.01263 |                  10 |        169,094 / 172,094 |                     63 / 4 |
| 1920×1080 | 0.00803 |                  10 |        169,094 / 172,094 |                     21 / 4 |

The strict suite confirmed Feed search/filter/pagination/history/empty/404,
focus and keyboard behavior, explicit reaction-participant activation,
post/detail/reaction/lazy-picker/reduced-motion behavior, icon-only Bridge,
exact footer/header order, theme persistence without hydration error, private
personalized APIs, responsive media, and the non-mutating auth/subscription/CMS
entry surfaces. It submitted no auth, OAuth, subscription, comment, reaction,
publication, scheduling, or CMS mutation.

## Performance baseline

The isolated restored PostgreSQL probe used three samples per route. Query
counts were stable and showed no Feed/detail/comments/reaction N+1 regression:

| Probe               | Query counts | Median server ms | Maximum response bytes |
| ------------------- | ------------ | ---------------: | ---------------------: |
| Feed page 1         | 4 / 4 / 4    |           14.664 |                  8,472 |
| Feed page 2         | 5 / 5 / 5    |           11.477 |                  5,345 |
| Unicode search      | 6 / 5 / 5    |           15.122 |                  2,318 |
| Tag filter          | 4 / 4 / 4    |           26.193 |                    921 |
| Tag catalog         | 2 / 2 / 2    |            5.368 |                    259 |
| Post detail         | 3 / 3 / 3    |            8.497 |                  1,015 |
| Comments            | 4 / 4 / 4    |           22.108 |                    478 |
| Post-reaction batch | 3 / 3 / 3    |           16.742 |                  3,360 |

Comments and reaction-batch responses were `private, no-store` with
`Vary: Cookie`. Network-facing browser metrics use the median of three
requests and are recorded separately because CDN/TLS/runner variance is not a
server-query regression signal. Their three-sample medians were 702 ms for
Feed, 731 ms for Unicode search, and 572 ms for detail. The verified
responsive-media probe requires all 480w/960w/1440w PNG renditions; each
returned `public, max-age=31536000, immutable`, and the rendered Feed image
exposed `sizes`, `srcset`, non-zero intrinsic width, and non-zero rendered
width. No broad or score-driven optimization was made.

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

## Remaining completion gate, backlog, and production blockers

All implementation, closed-gate CI, controlled rollout, pre-migration backup,
migration, health, schema-3 attestation, gate restoration, fresh recovery, data
and performance comparison, and five-viewport live gates have passed. The only
remaining Stage 18 gate is required push/PR CI for the documentation-only
commit containing this completion-candidate report; deployment and attestation
must remain skipped and catalog sync must remain skipped.

### P3 backlog

Rollback-only `ReactionSettings` quick-reaction fields and the internal Django
config endpoint remain intentionally. The frontend and exact public proxy
allowlist do not use or expose them. Remove them only after the rollback window
closes, with an explicit backward-compatible migration and cache strategy; no
schema contraction is justified during stabilization.

### Production blockers

Production remains blocked by the absence of a production Environment and all
production infrastructure/provider configuration, by the lack of a separately
approved production rollout/promotion decision, and independently by the 228
custom emoji items whose rights are still `staging-only/unverified`. Stage 18
does not approve, create, or promote production.
