# 0001: Version Baseline and Update Policy

- **Status:** Proposed
- **Date:** 2026-08-20
- **Owners:** Control Tower

## Context

The repository currently contains governance, product, and architecture documentation only. The preferred technology direction in [the architecture document](../architecture.md) names React, TypeScript, React Router, Gravity UI, TanStack Query, Tiptap, PostgreSQL, and TypeScript/Node.js server code, but it does not establish versions or a compatibility envelope.

Before a dependency-bearing milestone can create an application foundation, the project needs a reproducible version baseline and an update policy that does not depend on a package-manager choice. This ADR records published package metadata and lifecycle statements only. It installs nothing, selects no package manager, and does not prove runtime compatibility.

Official sources were checked at **2026-08-21T00:17:14Z**. The npm registry is authoritative here for exact package patch versions, `latest` dist-tag resolution, engines, peers, and package-to-package dependencies. Project documentation, changelogs, release pages, and the official Node.js and PostgreSQL version pages are authoritative for behavior, migration, release status, and lifecycle statements.

## Decision drivers

- Use an exact, stable, mutually compatible starting point before implementation begins.
- Prefer an active LTS runtime and a production PostgreSQL release over Current or prerelease lines.
- Keep package selection separate from package-manager, repository-topology, runtime, bundler, and deployment decisions.
- Treat published engine and peer ranges as a metadata compatibility envelope, not as proof that the application works.
- Make dependency changes reviewable, reproducible, and resistant to unreviewed drift.
- Preserve accepted ADRs as historical records and use superseding ADRs for later decision changes.

## Considered options

1. **Exact compatibility-first baseline.** Select exact patches that satisfy the published engine and peer constraints, while deferring installation and runtime validation. This is the proposed option.
2. **Always use the newest published line.** This would choose Node.js 26.7.0 Current, TypeScript 7.0.2, or PostgreSQL 19 Beta 3 solely because each is newer. It is rejected for this baseline: Current Node and prerelease PostgreSQL are not the production posture sought here, and TypeScript 7 still has a tooling compatibility gap despite being a stable production release.
3. **Use semver ranges or dist-tags in future manifests.** This is rejected because resolution could drift without an explicit decision or review.
4. **Adopt TypeScript 6 and 7 side by side.** The TypeScript team documents this transition path, but it adds two compiler/tooling paths before the project has selected its build and lint tooling. It is not accepted now.
5. **Defer every version until the application foundation.** This would mix version research with packaging and topology decisions and would make later milestones harder to review independently.

## Decision

### Proposed version baseline

The following exact versions are the proposed baseline:

| Компонент | Выбранная версия |
| --- | --- |
| Node.js | 24.19.0 LTS |
| PostgreSQL | 18.6 |
| TypeScript | 6.0.3 |
| react | 19.2.8 |
| react-dom | 19.2.8 |
| @types/react | 19.2.18 |
| @types/react-dom | 19.2.4 |
| react-router | 8.3.0 |
| @gravity-ui/uikit | 7.48.0 |
| @tanstack/react-query | 5.101.4 |
| @tiptap/core | 3.30.2 |
| @tiptap/react | 3.30.2 |
| @tiptap/starter-kit | 3.30.2 |
| @tiptap/pm | 3.30.2 |

Observed but not selected:

| Component | Observed version | Published status | Reason not selected |
| --- | --- | --- | --- |
| Node.js | 26.7.0 | Current | The production baseline uses the 24.19.0 LTS line. |
| TypeScript | 7.0.2 | Stable and npm `latest` | Stable release, but it has no stable programmatic API yet and tooling compatibility is still incomplete. |
| PostgreSQL | 19 Beta 3 | Prerelease beta | The PostgreSQL project does not advise running it in production. |

### Published version and compatibility evidence

Every row was verified at **2026-08-21T00:17:14Z**. `latest` below means the official npm `latest` endpoint resolved to that exact patch at verification time.

| Component | Selected exact version | Observed stable/latest/LTS | Dist-tag or status | Published engines, peers, or alignment | Official source |
| --- | --- | --- | --- | --- | --- |
| Node.js | 24.19.0 | 24.19.0 latest LTS; 26.7.0 latest release | 24 LTS; 26 Current | 24.19.0 is above React Router's Node minimum. | [Download](https://nodejs.org/en/download), [release status](https://nodejs.org/en/about/previous-releases) |
| PostgreSQL | 18.6 | 18.6 is the current minor for supported major 18 | Production release; 19 Beta 3 is prerelease | Database-driver, ORM, and migration integration is not yet tested. | [Versioning policy](https://www.postgresql.org/support/versioning/), [18.6 and 19 Beta 3 release](https://www.postgresql.org/about/news/postgresql-186-1711-1615-1519-1424-and-19-beta-3-released-3365/) |
| TypeScript | 6.0.3 | 7.0.2 stable/latest | 7.0.2 is npm `latest`; 6.0.3 is an exact published release | 6.0.3 declares Node `>=14.17`; 7.0.2 declares Node `>=16.20.0`. | [6.0.3 metadata](https://registry.npmjs.org/typescript/6.0.3), [latest metadata](https://registry.npmjs.org/typescript/latest), [6.0 announcement](https://devblogs.microsoft.com/typescript/announcing-typescript-6-0/), [7.0 announcement](https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/) |
| `react` | 19.2.8 | 19.2.8 latest; docs identify 19.2 as the latest minor | npm `latest` | Declares Node `>=0.10.0`; no peer dependencies. | [Registry](https://registry.npmjs.org/react/latest), [versions](https://react.dev/versions) |
| `react-dom` | 19.2.8 | 19.2.8 latest | npm `latest` | Requires `react ^19.2.8`; the baseline pins both to 19.2.8. | [Registry](https://registry.npmjs.org/react-dom/latest) |
| `@types/react` | 19.2.18 | 19.2.18 latest | npm `latest` | No Node engine; no non-empty peer range is published. | [Registry](https://registry.npmjs.org/%40types%2Freact/latest) |
| `@types/react-dom` | 19.2.4 | 19.2.4 latest | npm `latest` | Requires `@types/react ^19.2.0`; 19.2.18 satisfies it. | [Registry](https://registry.npmjs.org/%40types%2Freact-dom/latest) |
| `react-router` | 8.3.0 | 8.3.0 latest | npm `latest` | ESM-only; Node `>=22.22.0`; React and React DOM `>=19.2.7` (`react-dom` is optional in metadata). Selected Node 24.19.0 and React/DOM 19.2.8 satisfy these ranges. | [Registry](https://registry.npmjs.org/react-router/latest), [changelog](https://reactrouter.com/start/changelog), [v7-to-v8 guide](https://reactrouter.com/upgrading/v7#react-router-dom) |
| `@gravity-ui/uikit` | 7.48.0 | 7.48.0 latest | npm `latest` | Peers allow React, React DOM, and optional React types 19.x. The published artifact declares no Node engine. | [Registry](https://registry.npmjs.org/%40gravity-ui%2Fuikit/latest), [package page](https://www.npmjs.com/package/@gravity-ui/uikit) |
| `@tanstack/react-query` | 5.101.4 | 5.101.4 latest | npm `latest` | Peer allows React `^18 || ^19`; dependency aligns `@tanstack/query-core` exactly at 5.101.4. | [Registry](https://registry.npmjs.org/%40tanstack%2Freact-query/latest), [installation](https://tanstack.com/query/latest/docs/framework/react/installation), [TypeScript guidance](https://tanstack.com/query/latest/docs/framework/react/typescript) |
| `@tiptap/core` | 3.30.2 | 3.30.2 latest | npm `latest` | Peer requires `@tiptap/pm 3.30.2`; no Node engine is published. | [Registry](https://registry.npmjs.org/%40tiptap%2Fcore/latest), [release](https://github.com/ueberdosis/tiptap/releases/tag/v3.30.2) |
| `@tiptap/react` | 3.30.2 | 3.30.2 latest | npm `latest` | Requires exact core/pm 3.30.2; peers allow React, React DOM, and their types on 17, 18, or 19. | [Registry](https://registry.npmjs.org/%40tiptap%2Freact/latest), [React guide](https://tiptap.dev/docs/editor/getting-started/install/react) |
| `@tiptap/starter-kit` | 3.30.2 | 3.30.2 latest | npm `latest` | Published dependencies align core, pm, and included extensions at 3.30.2; no engine or peer range is published. | [Registry](https://registry.npmjs.org/%40tiptap%2Fstarter-kit/latest), [React guide](https://tiptap.dev/docs/editor/getting-started/install/react) |
| `@tiptap/pm` | 3.30.2 | 3.30.2 latest | npm `latest` | No Node engine or peer range is published. | [Registry](https://registry.npmjs.org/%40tiptap%2Fpm/latest) |

The React and React DOM runtime packages are deliberately fixed to the same patch. The React type packages are a separate linked family and are also updated together.

React Router 8 removed the `react-router-dom` re-export package. It is not part of this baseline. This ADR selects only `react-router`; M03 will select the router mode and any required `@react-router/*` packages, adapters, or server packages. The ESM-only publication and metadata ranges are known, but no SSR or runtime path has been exercised.

All direct Tiptap packages are fixed to 3.30.2. Starter Kit is only a starting package baseline: it does not automatically approve every included extension for the future production document schema. Ready-made Tiptap UI Components are outside this baseline. M09 will decide the production schema, extension allowlist, versioning, sanitization, and renderer compatibility. Later SSR/editor validation must explicitly test `immediatelyRender: false`.

### TypeScript 6/7 decision

TypeScript 7.0.2 is a stable production release and the npm `latest` version; it is not characterized as unstable. It is not selected because the TypeScript team states that 7.0 does not ship a stable programmatic API and identifies embedded-language and tooling workflows that still rely on TypeScript 6. TypeScript 6.0.3 is therefore the compatibility-first baseline while M04, M05, and M13 have not yet selected or validated the build, package, lint, and CI toolchain.

The documented dual TypeScript 6/7 arrangement is not accepted. It would introduce parallel compiler and tooling paths before the relevant tooling decisions exist. TypeScript 7 will be reconsidered after a stable programmatic API is available and compatibility with the selected tooling has been confirmed.

### Pin and update policy

- Every future direct dependency specification must be an exact version. Caret, tilde, wildcard, dist-tag, prerelease, and Git-ref specifications are prohibited.
- Linked families are updated and reviewed atomically:
  - `react` and `react-dom`;
  - `@types/react` and `@types/react-dom`;
  - `react-router` and the `@react-router/*` packages selected by M03;
  - every direct `@tiptap/*` package;
  - `@tanstack/react-query` and its aligned `@tanstack/query-core` resolution.
- M05 will choose the package manager. Once one is selected, its lockfile must be committed and frozen install must be mandatory.
- Transitive dependencies are controlled by the lockfile, not enumerated as baseline entries in this ADR.
- The exact Node.js patch must later be recorded consistently in every version carrier chosen by M05 and the runtime/deployment milestones.
- The PostgreSQL major/minor version is pinned separately from the future production container image digest. Image and artifact immutability remains a deployment decision.
- A patch or minor update requires a separate reviewed maintenance milestone covering release notes, engine and peer metadata, lockfile changes, and relevant tests.
- A major update, or any update that changes the compatibility envelope, requires a superseding ADR.
- An automated updater may propose changes, but it may not auto-merge or auto-deploy them.
- A security update may use an accelerated schedule, but it still requires review and the applicable rollout policy.
- Versions and metadata must be checked again immediately before the first dependency-bearing milestone.
- Active-LTS Node.js and the current minor of the selected PostgreSQL major must be checked again before the first runtime/deployment milestone.
- An accepted ADR is not rewritten to change a decision; a new superseding ADR records the change.

### Decision boundaries

This ADR decides only exact starting versions, their published metadata envelope, and update policy. The following remain planned and unauthorized in [the roadmap](../roadmap.md):

- M03: React Router mode, SSR/runtime/deployment model, and the `@react-router/*` package set;
- M04: bundler, build, and development model;
- M05: repository/package/runtime topology, package manager, version carriers, workspace layout, and lockfile format;
- M06: backend/API framework and API/error contracts;
- M07: ORM, PostgreSQL migrations, and schema compatibility;
- M08: sessions, email/password, OAuth, and CSRF architecture;
- M09: Tiptap schema, versioning, sanitization, and renderer compatibility;
- M10: worker, scheduler, durable outbox, and idempotency model;
- M11: object storage, CDN, and media processing;
- M12: search, ranking, pagination, and cache model;
- M13: testing strategy and required CI jobs;
- M14: deployment topology, environment isolation, promotion, rollback, backup, and restore.

No application foundation, dependency installation, runtime topology, package-manager choice, bundler choice, or deployment model follows from this Proposed ADR.

## Consequences

- The first dependency-bearing milestone has an exact candidate baseline and a defined metadata compatibility envelope.
- Future manifests cannot silently float direct dependencies, and linked package families cannot be reviewed as unrelated changes.
- The project accepts short-term staleness when a newer release has not passed the required review.
- TypeScript 7 performance benefits are deferred until its tooling compatibility can be validated without introducing an unapproved dual setup.
- The baseline creates validation obligations; it does not claim that installation, typing, rendering, SSR, hydration, editor behavior, database integration, or production artifacts work.
- Package-manager, runtime, application, infrastructure, CI, and deployment decisions remain independent milestones.

## Validation

This documentation-only milestone validates official published metadata and source statements. No dependency was installed and no build, typecheck, test, SSR, browser, editor, or database command was run.

The following validation debt is mandatory after the responsible milestones create the necessary foundation:

- install and frozen-lock verification;
- React/React DOM render and hydration checks;
- React Router SSR and selected-runtime smoke checks;
- Gravity UI theme, SSR, portal, and hydration checks;
- TanStack Query SSR hydration checks;
- Tiptap initialization, JSON round-trip, and SSR-boundary checks, including `immediatelyRender: false`;
- lint and typecheck compatibility across the selected toolchain;
- PostgreSQL driver, ORM, and migration integration;
- production artifact and container-image pinning.

Runtime compatibility remains explicitly unverified until those checks exist and pass.

## Risks

- A registry dist-tag, patch release, or lifecycle status can change before installation. Recheck immediately before the first dependency-bearing milestone.
- Published peer and engine ranges can be incomplete or more permissive than real behavior. Control this through the deferred integration and smoke checks rather than claiming support from metadata alone.
- React Router's ESM-only packaging can constrain later runtime and bundler choices. M03 and M04 must validate the chosen path.
- Gravity UI publishes no Node engine, so this ADR provides no Node compatibility guarantee for it.
- Type changes in TanStack Query may ship in a patch release. Exact pinning and reviewed upgrades limit unplanned type drift.
- Starter Kit can make an extension appear available before the production schema approves it. M09 must define an explicit schema and extension allowlist.
- PostgreSQL minor releases can require extra post-update steps. Maintenance review must include the applicable release notes.

## Follow-ups

- M02-A1, if separately authorized after independent review and Control Tower decision, may promote this ADR, link it from architecture, and finalize the roadmap status.
- M03-M05 must make the deferred router, bundler, topology, package-manager, lockfile, and version-carrier decisions.
- M06-M14 must make the deferred application, data, security, editor, job, storage, search, testing, and deployment decisions.
- The first dependency-bearing milestone must re-verify every selected version and all relevant engine/peer metadata before adding manifests.
- The first runtime/deployment milestone must re-verify active-LTS Node.js and the current PostgreSQL 18 minor.
- Reconsider TypeScript 7 after its stable programmatic API and selected-tooling compatibility are confirmed.
- Execute the validation debt only in the milestones that authorize the required code and tooling.

## Supersedes / Superseded by

None.
