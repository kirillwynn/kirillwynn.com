# 0004: Repository, Package, and Logical Runtime Topology

- **Status:** Proposed
- **Date:** 2026-08-22
- **Owners:** Control Tower

## Context

[ADR 0001](0001-version-baseline-and-update-policy.md) accepts exact application and runtime versions, including Node.js 24.19.0, and requires exact direct dependency specifications, an eventual committed lockfile, and frozen installation. [ADR 0002](0002-react-router-ssr-runtime-deployment-model.md) accepts React Router 8.3.0 Data Mode with project-owned custom SSR, browser hydration, a portable Web `Request` to `Response` boundary, and Node-compatible ESM server modules. [ADR 0003](0003-bundler-build-development-model.md) accepts Vite 8.2.2 with `@vitejs/plugin-react` 6.1.0, distinct browser and Node ESM production builds, default SSR dependency externalization, and a fail-closed browser reachability requirement.

Those Accepted ADRs deliberately do not choose a package manager, bootstrap broker, lockfile format, workspace layout, manifest ownership, dependency directions, logical runtime ownership, or production dependency closure. Without those decisions, a dependency-bearing implementation could create multiple lockfiles, hide undeclared imports through hoisting, ship an incomplete externalized SSR graph, or let server-only code become browser-reachable.

This Proposed ADR establishes a future repository contract only. It creates no manifest, workspace configuration, lockfile, Node version file, source, build configuration, script, workflow, generated artifact, dependency installation, or runtime claim. It defines logical runtime and package ownership, not deployed processes or services.

Official primary sources were reopened at the single cutoff **2026-08-22T17:38:05Z**. Exact registry records and tagged source describe immutable published artifacts; dist-tags and project documentation are rolling observations at the cutoff. Metadata compatibility is not install, build, SSR, hydration, or runtime compatibility.

### Official evidence matrix

| Claim | Direct official source | Evidence class and exact identity | UTC cutoff | Exact verified result |
| --- | --- | --- | --- | --- |
| The accepted Node release carries the bundled manager and broker versions used in this comparison. | [Node release index](https://nodejs.org/download/release/index.json), tagged Node source for [npm](https://github.com/nodejs/node/blob/v24.19.0/deps/npm/package.json) and [Corepack](https://github.com/nodejs/node/blob/v24.19.0/deps/corepack/package.json) | Versioned release and tag `v24.19.0` | 2026-08-22T17:38:05Z | Node 24.19.0 is Krypton LTS, dated 2026-08-03, and contains npm 11.17.0 and Corepack 0.35.0. |
| Bundled npm is compatible with the accepted Node version but is not the current npm major. | [`npm@11.17.0` metadata](https://registry.npmjs.org/npm/11.17.0), [`npm@12.0.2` metadata](https://registry.npmjs.org/npm/12.0.2), [`npm` latest](https://registry.npmjs.org/npm/latest) | Exact npm registry metadata and rolling `latest` | 2026-08-22T17:38:05Z | npm 11.17.0 declares Node `^20.17.0` or `>=22.9.0`; npm 12.0.2 is `latest` and declares Node `^22.22.2`, `^24.15.0`, or `>=26.0.0`. Node 24.19.0 satisfies both. |
| npm 12 has stronger install-source and lifecycle defaults than the bundled npm 11 line. | [npm 12 security-default announcement](https://github.blog/changelog/2026-06-09-upcoming-breaking-changes-for-npm-v12/), [npm configuration](https://docs.npmjs.com/using-npm/config/), [`npm ci`](https://docs.npmjs.com/cli/commands/npm-ci/) | Dated official announcement and rolling npm 12 documentation | 2026-08-22T17:38:05Z | npm 12 defaults dependency install scripts, Git dependencies, and remote URL dependencies to deny unless explicitly allowed; `npm ci` supplies the frozen-clean-install contract. |
| pnpm 11.22.0 is the current stable pnpm release and supports the accepted Node version. | [`pnpm@11.22.0` metadata](https://registry.npmjs.org/pnpm/11.22.0), [pnpm dist-tags](https://registry.npmjs.org/-/package/pnpm/dist-tags) | Exact registry metadata and rolling dist-tags | 2026-08-22T17:38:05Z | `latest` and `latest-11` are 11.22.0, its Node engine is `>=22.13`, and `next-12` is prerelease 12.0.0-rc.8. The selected tarball SRI is `sha512-H/hwxMYTPf2I+yr8Rt0T1H8JyXlLQ4xv20fKmMrzvBY4HuC+k6CRuOOCTPAfiJ9G19niCRD7C+GrD7W6qA3WIQ==`. |
| pnpm supplies a single workspace lockfile, strict isolated linker, exact local-workspace protocol, cycle failure, and frozen-install failure. | [workspace](https://pnpm.io/workspaces), [settings](https://pnpm.io/settings), [node-modules settings](https://pnpm.io/settings/node-modules), [`pnpm install`](https://pnpm.io/cli/install) | Rolling official pnpm 11/12 documentation | 2026-08-22T17:38:05Z | A workspace is rooted by `pnpm-workspace.yaml`; the default linker is `isolated`; a shared workspace lockfile is supported; `workspace:` refuses registry fallback; cycles can fail; `--frozen-lockfile` rejects a missing or stale lockfile; tarball-integrity mismatch is a hard failure. |
| pnpm exposes fail-closed dependency-script and dependency-policy controls. | [build settings](https://pnpm.io/settings/build), [supply-chain guidance](https://pnpm.io/supply-chain-security), [`approve-builds`](https://pnpm.io/cli/approve-builds), [peer settings](https://pnpm.io/settings/peer-dependencies), [CLI and Node settings](https://pnpm.io/settings/cli) | Rolling official pnpm 11/12 documentation | 2026-08-22T17:38:05Z | Unlisted dependency builds are disallowed; `strictDepBuilds` fails on unreviewed builds; `allowBuilds` records explicit allow/deny decisions; pnpm also documents strict peer, engine, exotic-subdependency, and minimum-release-age controls. |
| Yarn 4.18.0 is the current Yarn CLI distribution and has a credible immutable, script-denying alternative. | [`@yarnpkg/cli-dist@4.18.0` metadata](https://registry.npmjs.org/%40yarnpkg%2Fcli-dist/4.18.0), [`latest` metadata](https://registry.npmjs.org/%40yarnpkg%2Fcli-dist/latest), [`yarn install`](https://yarnpkg.com/cli/install), [Yarn settings](https://yarnpkg.com/configuration/yarnrc/) | Exact registry metadata and rolling Yarn documentation | 2026-08-22T17:38:05Z | 4.18.0 is `latest`, requires Node `>=18.12.0`, supports immutable install, and defaults third-party postinstall scripts off. Its default linker is Plug'n'Play rather than `node_modules`. |
| Corepack 0.35.0 is a broker, not the selected package manager, and can bind a manager version plus artifact hash. | [Corepack 0.35.0 README](https://github.com/nodejs/corepack/blob/v0.35.0/README.md), [`corepack@0.35.0` metadata](https://registry.npmjs.org/corepack/0.35.0) | Tagged documentation and exact registry metadata | 2026-08-22T17:38:05Z | Corepack is bundled before Node 25, mediates npm/Yarn/pnpm, validates `packageManager` name/version/hash, and Corepack 0.35.0 declares compatibility with Node 24.15.0 and later on the 24 line. |
| Volta is not a responsible new bootstrap baseline. | [official Volta repository](https://github.com/volta-cli/volta), [official pnpm support page](https://docs.volta.sh/advanced/pnpm) | Rolling official project status and documentation | 2026-08-22T17:38:05Z | The official repository says Volta is unmaintained, and its pnpm support remains experimental. |
| The accepted application and build packages remain metadata-compatible with Node 24.19.0. | Exact registry metadata for [`react`](https://registry.npmjs.org/react/19.2.8), [`react-dom`](https://registry.npmjs.org/react-dom/19.2.8), [`react-router`](https://registry.npmjs.org/react-router/8.3.0), [`vite`](https://registry.npmjs.org/vite/8.2.2), and [`@vitejs/plugin-react`](https://registry.npmjs.org/%40vitejs%2Fplugin-react/6.1.0) | Exact npm registry metadata | 2026-08-22T17:38:05Z | The accepted exact versions still exist; React Router is ESM-only and requires Node `>=22.22.0`; Vite and the React plugin require Node `^20.19.0` or `>=22.12.0`; their published peer ranges remain aligned. |
| The accepted compiler and React type packages remain published at their exact pins. | Exact registry metadata for [`typescript@6.0.3`](https://registry.npmjs.org/typescript/6.0.3), [`@types/react@19.2.18`](https://registry.npmjs.org/%40types%2Freact/19.2.18), and [`@types/react-dom@19.2.4`](https://registry.npmjs.org/%40types%2Freact-dom/19.2.4) | Exact npm registry metadata | 2026-08-22T17:38:05Z | TypeScript declares Node `>=14.17`; the React DOM types require React types `^19.2.0`; the selected exact pins remain inside the published envelope. |
| The accepted UI, query, and editor artifacts remain published and mutually aligned at their exact pins. | Exact registry metadata for [`@gravity-ui/uikit@7.48.0`](https://registry.npmjs.org/%40gravity-ui%2Fuikit/7.48.0), [`@tanstack/react-query@5.101.4`](https://registry.npmjs.org/%40tanstack%2Freact-query/5.101.4), [`@tiptap/core@3.30.2`](https://registry.npmjs.org/%40tiptap%2Fcore/3.30.2), [`@tiptap/react@3.30.2`](https://registry.npmjs.org/%40tiptap%2Freact/3.30.2), [`@tiptap/starter-kit@3.30.2`](https://registry.npmjs.org/%40tiptap%2Fstarter-kit/3.30.2), and [`@tiptap/pm@3.30.2`](https://registry.npmjs.org/%40tiptap%2Fpm/3.30.2) | Exact npm registry metadata | 2026-08-22T17:38:05Z | The selected artifacts exist; Gravity UI and TanStack Query allow React 19; the selected direct Tiptap packages remain aligned at 3.30.2. |
| One accepted application pin has dist-tag drift, which does not change the accepted version. | Exact [`@gravity-ui/uikit@7.48.0`](https://registry.npmjs.org/%40gravity-ui%2Fuikit/7.48.0) and rolling [`latest`](https://registry.npmjs.org/%40gravity-ui%2Fuikit/latest) metadata | Exact selected metadata and rolling dist-tag | 2026-08-22T17:38:05Z | The accepted 7.48.0 artifact remains published, while `latest` is 7.48.1, published 2026-08-21T14:28:52.553Z. ADR 0001 still requires 7.48.0; any update needs its maintenance review. |
| The selected logical package graph preserves custom Data Mode SSR and the two-build contract. | [React Router custom Data Mode integration](https://reactrouter.com/start/data/custom), [Vite SSR guide](https://vite.dev/guide/ssr) | Rolling official documentation | 2026-08-22T17:38:05Z | React Router supports project-owned browser/server Data Mode entries, and Vite documents distinct browser and SSR builds with SSR dependencies externalized by default. |

## Decision drivers

- Produce one deterministic manager, bootstrap path, workspace definition, and lockfile owner.
- Preserve every exact version and update rule accepted by ADR 0001, including Node.js 24.19.0.
- Keep undeclared dependencies unavailable to first-party packages and make workspace cycles fail.
- Default dependency lifecycle scripts to deny, require an auditable allowlist, and reject stale manifests, lockfiles, engine ranges, peers, and artifact integrity.
- Give each browser, server, shared, and future worker import graph one manifest owner and one allowed dependency direction.
- Preserve React Router Data Mode custom SSR and the distinct Vite browser and Node ESM builds.
- Make server-only reachability into the browser graph fail before artifact emission and assign ownership for the negative proof.
- Make every externalized production bare import part of an explicit production dependency closure.
- Keep backend, worker technology, test/CI tooling, deployed process count, provider, container, and shipping mechanics in their later milestones.
- Avoid introducing an unmaintained or unnecessary second toolchain/version carrier.

## Considered options

### Package manager and bootstrap

1. **pnpm 11.22.0 through Corepack 0.35.0.** This combines an exact hashed manager artifact, one workspace lockfile, isolated dependency visibility, exact local-workspace resolution, frozen-install failure, strict engine/peer controls, and default-denied dependency scripts. Corepack is already present in the accepted official Node distribution and remains only the bootstrap broker. This is selected.
2. **Bundled npm 11.17.0.** This has the smallest bootstrap surface and supports standard workspaces, `package-lock.json`, and `npm ci`. It is not selected because its hoisted layout gives weaker first-party dependency-boundary feedback and it predates npm 12's fail-closed dependency-script/source defaults.
3. **Current npm 12.0.2.** This is compatible with Node 24.19.0 and has strong security defaults. It is not selected because the accepted Node distribution bundles npm 11.17.0, so npm 12 would require a separate self-update/bootstrap path without providing pnpm's isolated workspace visibility.
4. **Yarn 4.18.0.** Yarn has strong immutable-install and lifecycle-script defaults. It is not selected because its default Plug'n'Play loader would add a distinct resolution/runtime integration surface; choosing its `node-modules` or pnpm linker would add another explicit compatibility choice without a demonstrated advantage over pnpm itself.
5. **Volta as Node and package-manager broker.** It would add a second project version carrier and shim layer. It is rejected because the official project is unmaintained and pnpm support is experimental.

Corepack is not a sixth package-manager option. It brokers the exact selected manager and is not a project dependency or a substitute for `pnpm-lock.yaml`.

### Repository and package topology

1. **One root private application package.** This is simple but merges browser, Node SSR/server, future worker, and shared dependencies into one manifest. It weakens reachability review and makes production closure broader than each runtime needs. It is not selected.
2. **One repository with a root private pnpm workspace and explicit private runtime packages.** This gives each import graph a manifest, keeps one lockfile, expresses dependency direction mechanically, and can reserve a worker boundary without selecting its technology or deployment. This is selected.
3. **Multiple repositories or independently locked subprojects.** This would duplicate governance, toolchain carriers, and lockfiles before independent release or deployment needs exist. It is not selected.

## Decision

This ADR proposes the following complete M05 contract. It remains non-authorizing until separately accepted, and even acceptance would not authorize dependency-bearing implementation.

### Exact manager, broker, and version carriers

The package manager is exactly **pnpm 11.22.0**. The root `package.json` must contain exactly:

- `packageManager`: `pnpm@11.22.0+sha512.1ff870c4c6133dfd88fb2afc46dd13d47f09c9794b438c6fdb47ca98caf3bc16381ee0be93a091b8e3824cf01f889f46d7d9e20910fb0be1ab0fb5baa80dd621`;
- `engines.node`: `24.19.0`;
- `engines.pnpm`: `11.22.0`;
- `private`: `true`; and
- `type`: `module`.

The `sha512` suffix is the hexadecimal form of the selected registry tarball's published SRI digest. Corepack uses it to validate the downloaded manager artifact. It does not validate project dependencies, replace registry signatures, or make the lockfile unnecessary.

The bootstrap broker is exactly the **Corepack 0.35.0 bundled with the official Node.js 24.19.0 distribution**. Project commands invoke the manager through `corepack pnpm`; no globally installed pnpm, npm self-update, Volta shim, downloaded shell installer, `npx`, or `pnpm dlx` is a bootstrap path. Before any package-manager operation, the future bootstrap must fail unless the running Node, Corepack, and brokered pnpm report exactly 24.19.0, 0.35.0, and 11.22.0 and Corepack accepts the root `packageManager` integrity.

Corepack strict project matching and integrity verification must remain enabled. Bypassing project-spec enforcement, strict manager matching, or artifact and signature verification is prohibited. A distribution that omits or changes the exact bundled Corepack fails bootstrap; it must not silently install another broker. Offline cache hydration and the eventual Node artifact source belong to M14.

The repository-wide Node carriers are exactly:

- `.node-version`, whose future contents are exactly `24.19.0` plus a final newline;
- root and every workspace `package.json`, each with exact `engines.node: 24.19.0`; and
- root `pnpm-workspace.yaml`, with exact `nodeVersion: 24.19.0` and `engineStrict: true`.

Every workspace manifest is private and has `type: module`. `.nvmrc`, `.tool-versions`, a Volta block, semver ranges, aliases, or a second Node carrier are prohibited. The carriers are one atomic review unit: a Node change updates all of them together under ADR 0001, and a manager change updates `packageManager` plus hash, `engines.pnpm`, pnpm configuration compatibility, and `pnpm-lock.yaml` together. Automatic Corepack pinning and unattended `corepack use` or `corepack up` are prohibited.

### Future repository and package layout

The repository remains one Git repository and becomes one root private pnpm workspace. The only initially authorized future package and package-control paths are:

| Future repository path | Owner | Required contract |
| --- | --- | --- |
| `package.json` | Workspace root | Private non-runtime coordinator; owns manager and Node carriers plus workspace-wide build/development tooling. It is not an application runtime entry and has no production runtime dependencies. |
| `pnpm-workspace.yaml` | Workspace root | Enumerates only the four exact package paths below and owns all pnpm project settings. A glob must not discover unreviewed packages. |
| `pnpm-lock.yaml` | Workspace root | Sole authoritative dependency lock for root and every workspace importer. It is committed and generated only by the selected manager. |
| `.node-version` | Workspace root | Exact human/tool Node carrier `24.19.0`; provisioning and shipping remain later concerns. |
| `packages/shared/package.json` | `@kirillwynn/shared` | Private `0.0.0` ESM package for explicitly cross-runtime, browser-safe contracts and implementation. It imports no other first-party runtime package. |
| `packages/web/package.json` | `@kirillwynn/web` | Private `0.0.0` ESM package that owns the browser hydration graph, shared route identity, browser-safe route implementation, and browser-boundary policy. |
| `packages/server/package.json` | `@kirillwynn/server` | Private `0.0.0` ESM package that owns the Node SSR/server entry, server route bindings, and externalized server runtime closure. It selects no server framework or adapter. |
| `packages/worker/package.json` | `@kirillwynn/worker` | Private `0.0.0` ESM ownership boundary reserved for future asynchronous/scheduled code. It creates no worker technology, entry, process, or service decision. |

`pnpm-workspace.yaml` must enumerate `packages/shared`, `packages/web`, `packages/server`, and `packages/worker` literally. A new manifest or package path requires a separately reviewed topology change. Nested lockfiles and competing `package-lock.json`, `npm-shrinkwrap.json`, `yarn.lock`, Bun lockfiles, Yarn configuration, or another manager carrier are prohibited.

All internal package references use the exact target package version, initially `workspace:0.0.0`. `workspace:*`, `workspace:^`, `workspace:~`, plain semver fallback, `link:`, and `file:` are prohibited. This preserves ADR 0001's exact-spec intent while making registry fallback impossible. All packages remain `private: true`; no pack, publish, registry-release, or public package contract is approved.

The package dependency graph is acyclic and directional:

```text
server -> web -> shared
server -> shared
worker -> shared
```

`shared` cannot depend on `web`, `server`, or `worker`; `web` cannot depend on or import `server` or `worker`; `server` and `worker` cannot depend on one another; and `worker` cannot depend on `web`. Cross-package imports use declared package exports and exact `workspace:` dependencies, never relative paths escaping a package root. Any later exception requires a topology review rather than an alias or hoist workaround.

### Linker, workspace, and dependency policy

The future root `pnpm-workspace.yaml` must make these behaviors explicit rather than relying on changing defaults:

- `nodeLinker: isolated`, `hoist: false`, an empty `publicHoistPattern`, and `shamefullyHoist: false`;
- `sharedWorkspaceLockfile: true` and `gitBranchLockfile: false`;
- `linkWorkspacePackages: false`, so only explicit `workspace:` specifications link locally;
- `savePrefix: ''` and `saveWorkspaceProtocol: true`, producing exact external versions and version-qualified `workspace:` specifications;
- `disallowWorkspaceCycles: true`;
- `autoInstallPeers: false`, `strictPeerDependencies: true`, and `resolvePeersFromWorkspaceRoot: false`;
- exact `nodeVersion: 24.19.0` with `engineStrict: true`;
- an explicit `allowBuilds` map, `strictDepBuilds: true`, and `dangerouslyAllowAllBuilds: false`;
- `blockExoticSubdeps: true`;
- `minimumReleaseAge: 1440` for newly resolved external versions;
- `verifyDepsBeforeRun: error`, so a project command cannot install implicitly; and
- `registry: https://registry.npmjs.org/` with `strictSsl: true`.

The initial `allowBuilds` map has no `true` entry. The first dependency-bearing milestone must inspect every blocked lifecycle script and record explicit `true` or `false` decisions. A `true` entry requires exact package/version evidence, purpose, expected outputs or side effects, and a negative review of alternatives; name-wide, wildcard, blanket, interactive-approve-all, and future-version approvals are prohibited. Project-authored scripts are not dependency install scripts and remain subject to later M13 command/tooling review.

Every non-optional peer required by the selected graph must be declared explicitly by the consuming workspace. Peer conflicts, missing peers, engine mismatch, workspace cycles, missing lockfiles, stale lockfiles, or tarball-integrity mismatch are hard failures. No peer-rule suppression, package extension, forced resolution, patch, or checksum refresh may be introduced without a separately reviewed, evidence-backed exception.

### Lockfile, install, registry, and update policy

`pnpm-lock.yaml` is one atomic repository artifact owned by the workspace root. It includes every importer and the complete resolution graph. The only reproducibility command for an unchanged checkout is `corepack pnpm install --frozen-lockfile`; frozen mode is mandatory in review validation, CI, production materialization, and any clean-room reproduction. An absent lockfile, manifest/config mismatch, importer drift, manager/lockfile incompatibility, or required lockfile rewrite fails.

Ordinary non-frozen install is permitted only in a separately authorized dependency or manager maintenance milestone whose purpose includes producing and reviewing the lockfile change. `--fix-lockfile`, `--update-checksums`, forced install, lockfile deletion/regeneration, and bypassing frozen mode are not repair shortcuts. A legitimate integrity change is treated as a new artifact requiring source verification and review.

External direct specifications are exact registry versions only, using the public HTTPS npm registry `https://registry.npmjs.org/`. Git, GitHub shorthand, branch, commit, remote tarball, direct URL, local directory, and dist-tag specifications are prohibited; internal packages use only exact `workspace:` specifications. TLS verification remains enabled. The selected public package graph requires no registry credentials, so no repository `.npmrc`, token, password, certificate, auth header, credential placeholder, or Corepack credential file is part of this contract. A private registry or authenticated package source requires a new decision; credentials must remain in trusted external environment or user-level configuration and never in Git.

Dependency updates follow ADR 0001. Exact direct versions, linked families, manager version/hash, pnpm policy, and resulting lockfile changes are reviewed together as applicable. The 1,440-minute age gate supplements review but never substitutes for it. Automated tooling may propose but not merge or deploy updates.

### Direct dependency classification and ownership

The accepted versions are not changed. Their future manifest classification is:

| Classification | Exact accepted packages | Manifest consequence |
| --- | --- | --- |
| Direct application runtime | `react@19.2.8`, `react-dom@19.2.8`, `react-router@8.3.0` | `packages/web` declares every package it imports. `packages/server` also declares each package that it imports directly or that remains as an external bare import in its built Node ESM graph. `react-dom` remains direct even though React Router marks it optional, because hydration and SSR import its browser/server subpaths. |
| Conditional direct application runtime | `@gravity-ui/uikit@7.48.0`, `@tanstack/react-query@5.101.4`, `@tiptap/core@3.30.2`, `@tiptap/react@3.30.2`, `@tiptap/starter-kit@3.30.2`, `@tiptap/pm@3.30.2` | The workspace that imports one declares it in `dependencies` at the accepted exact version. Acceptance of a package baseline does not force an unused package into a manifest. The Gravity UI pin remains 7.48.0 despite `latest` drift. |
| Build/development | `vite@8.2.2`, `@vitejs/plugin-react@6.1.0`, `typescript@6.0.3`, `@types/react@19.2.18`, `@types/react-dom@19.2.4` | The root manifest owns Vite, the React plugin, and TypeScript as exact `devDependencies`; `packages/web/package.json` owns the two React type packages as exact `devDependencies`. They are not part of a production runtime closure merely because they build it. |
| Transitive unless first-party code imports it | React Router's `cookie-es` and other packages reached only through the lockfile graph | Do not promote a transitive package to direct. If first-party source starts importing its bare specifier, the owning workspace must declare the exact direct version under ADR 0001 review. |
| Not selected | `@react-router/dev`, `@react-router/node`, `@react-router/express`, `@react-router/serve`, Router Framework packages, backend/server adapters, optional React compiler or Vite plugin peers, direct Rolldown/esbuild additions, and unaccepted plugins | No manifest may add these through M05. M06 or a superseding ADR must select a backend/adapter; optional tooling needs its own authorized evidence. |

Package classification follows actual import and execution ownership, not convenience. Runtime code may not depend on root-only dev tooling. A build tool's transitive package does not become an application runtime dependency, and a package available through the shared store or lockfile is not import permission.

### Logical runtime ownership and build preservation

The physical workspace expresses these logical boundaries:

| Logical boundary | Owning manifest | Allowed reachability and obligation | Deferred decisions |
| --- | --- | --- | --- |
| Browser hydration | `packages/web/package.json` | Browser entry, browser-safe route graph, shared UI, and browser-safe `shared` exports only. It produces ADR 0003's browser assets/manifests and must reject server/worker reachability before emission. | Browser source paths, route tree, application features, and M13 test tooling. |
| Node ESM SSR/server | `packages/server/package.json` | Server entry, server route bindings, explicit SSR-safe `web` export, and `shared`. It produces ADR 0003's Node ESM server build and preserves ADR 0002's Web `Request` to `Response` boundary. | M06 framework/adapter/API/header/error implementation and M14 shipping/process topology. |
| Cross-runtime shared | `packages/shared/package.json` | Only code deliberately safe for every importing graph; no secrets, privileged clients, Node-only implementation, browser global assumption, or reverse runtime dependency. | Concrete domain contracts in their owning later milestones. |
| Future worker | `packages/worker/package.json` | Reserved manifest and dependency boundary that may reach `shared` only until M10 decides more. The repository ESM/version carriers apply, but no executable worker, scheduler, queue, runtime technology, or process is selected. | M10 worker/scheduler/outbox/idempotency technology and M14 deployment/process topology. |

There remains one logical React Router route graph with stable identities. `web` owns the browser-safe identity and implementation surface; `server` owns server bindings and consumes only an explicit SSR-safe `web` surface. The Vite browser build starts from the browser graph, and the distinct Vite SSR build starts from the Node ESM server graph. This does not select Framework Mode, `@react-router/dev`, a filesystem route convention, the Environment API, another bundler, or a backend framework.

`packages/web` owns the fail-closed browser boundary. Its future browser build policy must use an allowlist of browser-safe package roots/exports and reject, rather than externalize or warn about, any direct or transitive import of `packages/server`, `packages/worker`, Node built-ins, secrets, database clients, privileged services, or a server-only marker. The isolated workspace graph is the first control, not the complete proof: the Vite reachability guard must also catch path aliases and relative-path escape attempts. The negative fixture belongs to `packages/web` and must deliberately make a server-only sentinel browser-reachable; the browser build must exit non-zero before emitting artifacts. M13 selects the test mechanism, but it may not weaken this ownership or negative proof.

### Production dependency closure

Each executable logical runtime has one owning manifest. For every built Node SSR/server or future worker entry, every non-built-in bare package specifier left external in the entry or any reachable chunk, including conditional and dynamic imports, must map to a direct exact `dependencies` entry in that runtime's owning manifest. A subpath such as `react-dom/server` maps to the `react-dom` package. Undeclared, peer-only, root-dev-only, hoisted, or merely lockfile-present packages do not satisfy this rule.

An internal runtime dependency is exact `workspace:0.0.0`; its own production dependencies join the recursive closure in the single lockfile. Browser-bundled packages still remain direct dependencies of the source package that imports them, but browser assets do not require a server-side production install merely because they were bundled.

The future production-closure proof must begin with the owning manifest and the frozen root lockfile, traverse only production workspace/dependency edges, and compare that result with every external bare import in emitted runtime artifacts. It must include required optional/platform artifacts for the selected target and fail on missing or surplus undeclared runtime imports. The lockfile does not prove cross-platform behavior, native binary compatibility, or bit-for-bit reproduction.

M05 defines this closure invariant only. M14 retains ownership of pruning/materialization commands, artifact directories, production installation, shipping, containers, operating system, CPU/libc target, provider, process/service count, co-location, promotion, and rollback.

### Decision boundaries

| Source or later milestone | Preserved or deferred boundary |
| --- | --- |
| ADR 0001 | Preserves Node 24.19.0 and every accepted direct dependency version. Direct external specs stay exact; linked families and updates remain atomic/reviewed. |
| ADR 0002 | Preserves Data Mode custom SSR, buffered initial rendering, hydration, the shared logical route graph, and portable Web `Request` to `Response`. No Framework Mode or Router adapter is added. |
| ADR 0003 | Preserves Vite 8.2.2/plugin 6.1.0, distinct browser/Node ESM builds, manifests, default SSR externalization, and fail-closed browser reachability. No Environment API mandate or optional plugin is added. |
| M06 | Chooses backend/server framework, React Router adapter, concrete HTTP/header/error integration, API and mutation contracts, and authorization integration. |
| M07-M09 | Choose persistence/migrations, auth/session/CSRF, and editor schema/sanitization. Package ownership here grants none of those decisions. |
| M10 | Chooses worker technology, scheduling, durable outbox, idempotency, and executable worker boundaries. The reserved package is not that decision. |
| M11-M12 | Choose storage/CDN/media and search/ranking/pagination/cache contracts. |
| M13 | Chooses scripts, typecheck/test/lint tools, executable validation commands, CI jobs, and required checks. M05 specifies invariants, not those tools. |
| M14 | Chooses build/runtime stages, dependency materialization/shipping, containers, provider, OS/CPU/libc target, deployed process/service count, co-location, environments, promotion, rollback, backup, and restore. |

No backend framework, worker technology, runtime process count, service split, container, deployment unit, provider, domain, port, reverse proxy, production directory, staging action, or co-location follows from the words `web`, `server`, or `worker` in this ADR.

## Consequences

- The project receives one exact manager artifact, one bundled broker, one workspace definition, and one authoritative lockfile.
- Private package manifests make browser, SSR/server, shared, and future worker ownership reviewable without claiming separate deployed services.
- Isolated linking and exact `workspace:` edges expose undeclared and cyclic first-party dependencies earlier.
- Strict peer, engine, source, integrity, lifecycle-script, and frozen-lock policies intentionally convert ambiguity into installation failure.
- The default-empty lifecycle allowlist may block a legitimate native or build dependency; review and the narrowest exact approval are required before it can run.
- `react`, `react-dom`, and `react-router` may appear in more than one runtime manifest when each owner imports or externalizes them. The shared lockfile still resolves one reviewed graph; avoiding duplicate declarations is less important than complete runtime ownership.
- Root build/dev tooling is excluded from production closure unless a runtime artifact actually imports it, which would itself require review.
- The custom Data Mode and two-build contracts remain intact, while package topology makes the server/browser partition and negative proof expressible.
- Publishing and independently versioned packages remain unavailable; `0.0.0` is an internal exact workspace identity, not a release promise.
- Implementation, CI, and deployment work remain blocked until their own milestones authorize files, dependencies, commands, and external changes.

## Validation

M05 validation is documentation-only. No dependency was installed; no package manager or Corepack bootstrap was run; and no build, typecheck, test, lint, development server, SSR, hydration, runtime, worker, or deployment command was executed.

The first dependency-bearing implementation must recheck exact registry metadata at its own cutoff and provide executable evidence for all of the following before claiming package or runtime compatibility:

- exact Node 24.19.0, bundled Corepack 0.35.0, brokered pnpm 11.22.0, and root `packageManager` hash checks, including failure fixtures for each mismatch;
- exact agreement among `.node-version`, every manifest engine, and `pnpm-workspace.yaml`;
- one root workspace, exactly four initial private importers, one root `pnpm-lock.yaml`, and no competing manager/lockfile/config carrier;
- clean `corepack pnpm install --frozen-lockfile` from a fresh dependency state, followed by a second frozen install that leaves tracked inputs unchanged;
- frozen-install failure for an absent/stale lockfile, manifest drift, workspace-config drift, manager mismatch, engine mismatch, peer mismatch, workspace cycle, prohibited source, and integrity mismatch;
- review of every dependency lifecycle script with no unlisted or blanket-approved build and a negative unreviewed-script fixture;
- proof that first-party source cannot import an undeclared dependency, a disallowed reverse workspace edge, or a relative escape across package roots;
- both ADR 0003 production builds, Node 24.19.0 ESM import of the server entry, and preservation of ADR 0002 Data Mode SSR/hydration behavior;
- the browser-boundary negative fixture failing before emission plus artifact scans for server-only identifiers, Node built-ins, private paths, and secret values;
- a machine-derived comparison of every external runtime bare import against the owning manifest's direct production dependencies and recursive frozen-lock closure; and
- target-specific optional/native dependency validation before M14 can select production materialization or shipping.

M13 owns the eventual test/typecheck/lint frameworks, scripts, CI jobs, and enforcement wiring. M14 owns production materialization and shipping. Listing required evidence here does not authorize those implementations.

## Risks

- Corepack is not bundled with Node 25 and may be omitted by third-party Node distributions. The exact accepted official Node 24.19.0 distribution avoids silent drift now, but the bootstrap choice must be revisited with any Node major change.
- A `packageManager` digest validates the manager tarball bytes, not the trustworthiness of all manager code, registry metadata, dependency tarballs, or transitive behavior. Registry verification and lockfile integrity remain separate controls.
- pnpm's isolated symlink layout may expose compatibility problems in a future tool, native package, or serverless platform. A compatibility failure requires evidence and a reviewed exception; M05 does not pre-select a hoisted fallback or provider.
- Strict peers and disabled automatic peer installation can reveal incomplete third-party metadata. Suppressing the error could hide a real runtime mismatch, so exceptions require exact proof.
- The initial dependency graph may include a legitimate install script. Default-deny intentionally blocks it until the exact package/version and outputs are reviewed.
- Package direction alone cannot block relative-path or alias escapes. The browser build guard and negative fixture remain mandatory.
- Default Vite SSR externalization can leave an import that source-level manifest review misses. The emitted-artifact closure comparison is therefore blocking.
- A single lockfile records platform alternatives but does not prove every OS, CPU, libc, or native binary works. M14 must select and validate the actual production target.
- The `shared` package can become an accidental dumping ground that weakens boundaries. It must remain cross-runtime and browser-safe, with runtime-specific work kept in its owner.
- Rolling pnpm, Corepack, npm, Yarn, React Router, and Vite documentation can change after the cutoff. Exact metadata and material behavior must be rechecked before implementation or update.
- Gravity UI `latest` has already moved to 7.48.1. Installing the dist-tag would violate ADR 0001; the accepted 7.48.0 pin remains intentional staleness until reviewed.

## Follow-ups

- M05-A1 may record Control Tower acceptance after an Independent Reviewer returns no findings; it must not rewrite this technical decision or authorize implementation.
- The first dependency-bearing milestone must create only the authorized future carriers/manifests/configuration/lockfile, recheck all exact metadata, review lifecycle scripts, and produce the validation evidence above.
- M06 must select the server framework and adapter without changing the package graph, Data Mode contract, or build model implicitly.
- M10 must decide worker technology and executable ownership; the reserved package does not prejudge process or service topology.
- M13 must select the validation tooling, scripts, and CI enforcement for frozen install, boundaries, typecheck, builds, runtime closure, and negative fixtures.
- M14 must decide the Node artifact source, offline Corepack hydration if needed, production dependency materialization, native/platform target, artifact shipping, deployed processes/services, provider, promotion, and rollback.
- Any Node, Corepack, pnpm, lockfile-format, linker, package-boundary, direct dependency, or Gravity UI update follows ADR 0001 and, where it changes this decision, requires a superseding ADR.
- M06-M14 remain Planned and unauthorized until separately activated by Control Tower.

## Supersedes / Superseded by

None.
