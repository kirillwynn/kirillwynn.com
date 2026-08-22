# 0003: Bundler, Build, and Development Model

- **Status:** Accepted
- **Date:** 2026-08-21
- **Owners:** Control Tower

## Context

[ADR 0001](0001-version-baseline-and-update-policy.md) accepts the exact Node.js 24.19.0, TypeScript 6.0.3, React and React DOM 19.2.8, and React Router 8.3.0 baseline, ESM, and the exact-pin/update policy. [ADR 0002](0002-react-router-ssr-runtime-deployment-model.md) accepts React Router Data Mode with project-owned custom SSR, one shared logical route graph, buffered initial-document rendering, browser hydration, and a portable Web `Request` to `Response` boundary. Control Tower accepted M03-A1 on 2026-08-21; that lifecycle fact remains recorded in [the roadmap](../roadmap.md). Control Tower accepted M04 on 2026-08-22; M04-A1 records that decision and does not prove runtime compatibility or authorize implementation or M05.

Those earlier ADRs intentionally left the bundler, production build graph, artifact contract, and development behavior open. ADR 0003 now accepts the exact build contract below. Framework Mode and `@react-router/dev` remain unselected. Selecting Vite here does not change the accepted Router mode or grant authority to select a server framework, repository topology, deployment topology, or later-milestone tooling.

This is a documentation-only accepted decision record. It adds no dependency, package manifest, lockfile, build configuration, script, source file, generated artifact, workflow, or runtime claim. Published engine and peer ranges establish metadata compatibility only. No install, build, typecheck, test, development server, SSR, hydration, or runtime compatibility has been exercised.

Official evidence was reopened at the single cutoff **2026-08-21T22:29:39Z**. The evidence classes are deliberately separate:

- **Exact version metadata** is an exact npm registry record and describes the published package artifact at that version.
- **Tagged/version-specific evidence** is tied to the named release, tag object, tag commit, or versioned manifest.
- **Rolling official documentation** describes the official behavior visible at the cutoff but may change without changing an already-published package.
- Satisfying metadata ranges is **metadata compatibility**, not install, build, SSR, hydration, or runtime compatibility.

### Evidence matrix

Every result below was verified at the same UTC cutoff. Official rolling documents are evidence for the accepted contract, not permission to adopt sample paths, scripts, packages, servers, containers, or providers.

| Claim | Direct official source | Evidence class and exact identity | UTC cutoff | Exact verified result |
| --- | --- | --- | --- | --- |
| Vite 8 is the stable Rolldown-based major and publishes the relevant Node floor. | [Vite 8 announcement](https://vite.dev/blog/announcing-vite8) | Dated/version-specific stable-major announcement; page footer at `de1111ab` | 2026-08-21T22:29:39Z | Vite 8 is stable, uses Rolldown as its unified bundler, and documents Node 20.19+ or 22.12+. |
| The selected Vite patch has the contracted Git identity. | [release](https://github.com/vitejs/vite/releases/tag/v8.2.2), [tag ref](https://api.github.com/repos/vitejs/vite/git/ref/tags/v8.2.2), [annotated tag object](https://api.github.com/repos/vitejs/vite/git/tags/7c0113b8b22adc0a9ad1aebfd8500192f6e1f90c), [commit](https://github.com/vitejs/vite/commit/de1111ab0be00879b404e7ed3b2a80e264edddc1) | Tagged/version-specific: `v8.2.2`; tag object `7c0113b8b22adc0a9ad1aebfd8500192f6e1f90c`; commit `de1111ab0be00879b404e7ed3b2a80e264edddc1` | 2026-08-21T22:29:39Z | The annotated tag dereferences to the contracted commit; the release is immutable and signed. |
| The exact Vite artifact publishes the contracted version and Node range. | [versioned manifest](https://github.com/vitejs/vite/blob/v8.2.2/packages/vite/package.json), [exact npm metadata](https://registry.npmjs.org/vite/8.2.2) | Exact version metadata: `vite@8.2.2` | 2026-08-21T22:29:39Z | `version` is `8.2.2`; `engines.node` is `^20.19.0` or `>=22.12.0`; Node.js 24.19.0 is inside that range. The npm record publishes shasum `399aefad3656145145be110d137a07ea5bb55014`. |
| The selected React plugin has the contracted identity and compatible Vite peer. | [release](https://github.com/vitejs/vite-plugin-react/releases/tag/plugin-react%406.1.0), [tag ref](https://api.github.com/repos/vitejs/vite-plugin-react/git/ref/tags/plugin-react%406.1.0), [versioned manifest](https://github.com/vitejs/vite-plugin-react/blob/plugin-react%406.1.0/packages/plugin-react/package.json), [exact npm metadata](https://registry.npmjs.org/%40vitejs%2Fplugin-react/6.1.0) | Tagged/version-specific and exact metadata: `plugin-react@6.1.0`; commit `39b31735bf79c2dd380eedaba7ed849256f92a29` | 2026-08-21T22:29:39Z | `version` is `6.1.0`; `engines.node` is `^20.19.0` or `>=22.12.0`; peer `vite` is `^8.0.0`; npm `gitHead` equals the tag commit. Node.js 24.19.0 and Vite 8.2.2 are inside the published ranges. Optional React Compiler peers are metadata, not selected packages or features. |
| Vite documents a low-level custom SSR flow and separate client and SSR production builds. | [SSR guide](https://vite.dev/guide/ssr) | Rolling official documentation | 2026-08-21T22:29:39Z | The guide documents middleware mode, `appType: "custom"`, `transformIndexHtml`, `ssrLoadModule`, SSR stack correction, separate client/SSR builds, production loading of the SSR artifact, module invalidation, and default SSR dependency externalization. |
| Vite manifests expose emitted files and dependency relationships. | [backend integration](https://vite.dev/guide/backend-integration), [build options](https://vite.dev/config/build-options) | Rolling official documentation | 2026-08-21T22:29:39Z | The browser manifest maps logical source keys to emitted files, static imports, dynamic imports, CSS, and assets; `build.manifest`, `build.ssrManifest`, SSR output, and clean-output behavior are documented build capabilities. |
| An SSR manifest does not independently identify request-used modules. | [SSR preload guidance](https://vite.dev/guide/ssr#generating-preload-directives) | Rolling official documentation | 2026-08-21T22:29:39Z | The manifest maps module IDs to browser files, but the rendering integration must separately collect the module IDs actually used by a request before it can emit route-aware preload directives. |
| Vite 8 documents the accepted browser target, minification, source-map, and clean-build baselines. | [build options](https://vite.dev/config/build-options) | Rolling official documentation for Vite 8 | 2026-08-21T22:29:39Z | `baseline-widely-available` is fixed for Vite 8 at 2026-01-01 and resolves to Chrome 111, Edge 111, Firefox 114, Safari 16.4, and iOS 16.4; client minification defaults to Oxc, SSR minification to off, production source maps to off, and output clearing to on when safely scoped. |
| Vite exposes browser constants at build time and warns that `VITE_*` values are public. | [environment variables and modes](https://vite.dev/guide/env-and-mode) | Rolling official documentation | 2026-08-21T22:29:39Z | `import.meta.env` constants are statically replaced; `VITE_*` values are bundled into client code and must not contain sensitive information. |
| Vite transforms TypeScript but does not typecheck, and provides first-party React Fast Refresh integration. | [features](https://vite.dev/guide/features) | Rolling official documentation | 2026-08-21T22:29:39Z | Vite documents transpile-only TypeScript behavior, separate static analysis, native ESM HMR, first-party React Fast Refresh, static dynamic-import splitting, and imported asset/CSS handling. |
| The Environment API is not a stable mandatory baseline. | [Environment API status](https://vite.dev/guide/api-environment) | Rolling official documentation | 2026-08-21T22:29:39Z | The API is in release-candidate phase and includes APIs still marked experimental; stabilization with potential breaking changes is deferred to a future major. |
| React Router supports project-owned Data Mode browser/server integration without `@react-router/dev`. | [custom Data Mode integration](https://reactrouter.com/start/data/custom), [route objects](https://reactrouter.com/start/data/route-object) | Rolling official documentation for the accepted React Router line | 2026-08-21T22:29:39Z | The guide documents browser and server Data Router APIs, shared route objects, Web requests/responses, hydration, and lazy route implementation properties while matching fields remain known up front. |
| The Webpack snapshot exists and supports mature multi-configuration, target, splitting, dev-server, and stats primitives. | [webpack metadata](https://registry.npmjs.org/webpack/5.109.2), [CLI metadata](https://registry.npmjs.org/webpack-cli/7.2.2), [dev-server metadata](https://registry.npmjs.org/webpack-dev-server/6.0.0), [configuration](https://webpack.js.org/concepts/configuration/), [targets](https://webpack.js.org/concepts/targets/), [dev server](https://webpack.js.org/configuration/dev-server/), [code splitting](https://webpack.js.org/guides/code-splitting/), [stats JSON](https://webpack.js.org/api/stats/) | Exact metadata: `webpack@5.109.2` (`gitHead` `6a24bd65b72c43207c36ce61b54e1f5833486906`), `webpack-cli@7.2.2` (`fb50f766851f500ca12867a2aa9de81fa6e368f9`), `webpack-dev-server@6.0.0` (`05cb7921b2cd216f8caa74d2bdcc39b3f0d05bea`); rolling docs | 2026-08-21T22:29:39Z | All exact artifacts exist. Webpack documents multiple client/server configurations, web and Node targets, dynamic-import splitting, a development server, and machine-readable stats, but these are primitives requiring project orchestration. |
| Webpack's Node ESM output remains experimental and built-in TypeScript does not cover TSX or typechecking. | [ESM output](https://webpack.js.org/configuration/output/#outputmodule), [TypeScript experiment](https://webpack.js.org/configuration/experiments/#experimentstypescript) | Rolling official documentation for Webpack 5 | 2026-08-21T22:29:39Z | `output.module` requires `experiments.outputModule` and is described as experimental/not fully supported; the built-in TypeScript transform erases types, does not typecheck, and does not handle JSX/TSX or non-erasable syntax. |
| Exact React Refresh plugin 0.6.2 does not peer-support webpack-dev-server 6. | [exact plugin metadata](https://registry.npmjs.org/%40pmmmwh%2Freact-refresh-webpack-plugin/0.6.2), [rolling project README](https://github.com/pmmmwh/react-refresh-webpack-plugin) | Exact metadata: `@pmmmwh/react-refresh-webpack-plugin@0.6.2`; rolling README classified separately | 2026-08-21T22:29:39Z | The 0.6.2 peer accepts `webpack-dev-server` `^4.8.0` or `5.x`, excluding 6. The rolling README now lists 6.x too, but it is not version-specific evidence for the 0.6.2 artifact. |
| The Rspack snapshot exists and Rspack 2 makes ESM output non-experimental. | [core metadata](https://registry.npmjs.org/%40rspack%2Fcore/2.1.10), [CLI metadata](https://registry.npmjs.org/%40rspack%2Fcli/2.1.10), [dev-server metadata](https://registry.npmjs.org/%40rspack%2Fdev-server/2.2.0), [refresh metadata](https://registry.npmjs.org/%40rspack%2Fplugin-react-refresh/2.0.2), [2.0 announcement](https://www.rspack.dev/blog/announcing-2-0), [2.1 announcement](https://www.rspack.dev/blog/announcing-2-1), [v2 migration](https://www.rspack.dev/guide/migration/rspack_1.x), [output](https://www.rspack.dev/config/output#outputmodule) | Exact metadata: `@rspack/core@2.1.10`, `@rspack/cli@2.1.10`, `@rspack/dev-server@2.2.0`, `@rspack/plugin-react-refresh@2.0.2`; rolling docs | 2026-08-21T22:29:39Z | All exact artifacts exist. Rspack 2 removes `experiments.outputModule` and configures `output.module` directly; the 2.x line is stable but recent. |
| Rspack provides built-in SWC/TSX and a maintained React Refresh path while retaining plugin differences. | [target](https://www.rspack.dev/config/target), [React integration](https://www.rspack.dev/guide/tech/react), [TypeScript integration](https://www.rspack.dev/guide/tech/typescript), [plugin API](https://www.rspack.dev/api/plugin-api/) | Rolling official documentation | 2026-08-21T22:29:39Z | Built-in SWC handles TS/TSX transformation without typechecking; the maintained refresh plugin covers injection with SWC/Babel transforms; Rspack documents broad Webpack plugin compatibility but also subtle API differences. No official primitive supplies this project's complete Data Mode SSR orchestration or semantic route-to-asset contract. |
| Standalone Rolldown is a capable bundler but Vite is the recommended application-level experience. | [exact metadata](https://registry.npmjs.org/rolldown/1.2.5), [introduction](https://rolldown.rs/guide/introduction), [getting started](https://rolldown.rs/guide/getting-started) | Exact metadata: `rolldown@1.2.5`; rolling official documentation | 2026-08-21T22:29:39Z | The exact artifact exists. Rolldown documents TypeScript/JSX, splitting, watch, and general bundling, but HMR remains work in progress and its guide recommends Vite for application dev server, HMR, and optimized production builds. |
| esbuild is production-used but lacks JavaScript HMR and retains splitting limitations. | [exact metadata](https://registry.npmjs.org/esbuild/0.28.2), [API](https://esbuild.github.io/api/), [production readiness](https://esbuild.github.io/faq/#production-readiness) | Exact metadata: `esbuild@0.28.2`, `gitHead` `609683d892977362a0f99026cb74b96263d728a9`; rolling official documentation | 2026-08-21T22:29:39Z | The exact artifact exists. JavaScript hot reload is out of scope for esbuild; code splitting is described as work in progress, ESM-only, with a known ordering issue; the project calls esbuild a late-stage beta. |

## Decision drivers

- Preserve the accepted React Router 8.3.0 Data Mode and project-owned SSR boundary without adopting Framework Mode or `@react-router/dev`.
- Produce separate, reviewable browser and Node ESM server builds from one logical route graph.
- Make browser/server reachability fail closed so server-only code and private values cannot enter browser artifacts.
- Define machine-consumable browser and SSR asset manifests without selecting repository or provider paths.
- Provide direct-document SSR, hydration, React Fast Refresh, and actionable client/server errors during development.
- Support TypeScript and TSX transformation while keeping exact TypeScript 6.0.3 typechecking an independent contract.
- Minimize project-owned build and HMR orchestration while retaining a custom server boundary.
- Keep package installation, topology, backend, testing/CI, and deployment decisions in their authorized later milestones.
- Prefer stable documented APIs and reject release-candidate, experimental, deprecated, or unnecessary integration layers.

## Considered options

### Vite 8

The exact candidate is `vite@8.2.2` with `@vitejs/plugin-react@6.1.0`. Vite documents the required low-level custom SSR flow, separate browser and SSR production builds, a Node-targeted server graph, middleware-mode development, first-party React Fast Refresh, browser and SSR manifests, TypeScript/TSX transformation, and default SSR dependency externalization. These capabilities integrate directly with the accepted Data Mode; `@react-router/dev` is not required.

This is the selected option because it supplies the most complete build and development layer while leaving the Router and server abstractions project-owned. Its costs are material: Vite 8's Rolldown architecture is recent, the custom SSR integration remains project-owned, and route-aware preload still needs project-owned request/module tracking. The Environment API is not used as the mandatory baseline while it remains release-candidate with experimental surfaces.

### Webpack 5

The comparison snapshot is `webpack@5.109.2`, `webpack-cli@7.2.2`, and `webpack-dev-server@6.0.0`. Webpack has a mature ecosystem, explicit web/Node targets, multi-configuration support, dynamic-import splitting, development-server primitives, and detailed stats JSON.

It is not selected. This project would own dual-compiler coordination, custom development SSR orchestration, React refresh integration, a TSX transformer, CSS extraction/order behavior, and a build-manifest-to-route contract. Node ESM output still goes through `experiments.outputModule`, which the official documentation calls experimental and not fully supported. React Fast Refresh is not built in. The exact `@pmmmwh/react-refresh-webpack-plugin@0.6.2` artifact peers with webpack-dev-server 4.8+/5.x, not the selected server 6.0.0 snapshot, even though the rolling project README has since added 6.x. Webpack stats can feed a project-owned manifest, but it is not itself this project's semantic browser/SSR route asset contract.

### Rspack 2

The comparison snapshot is `@rspack/core@2.1.10`, `@rspack/cli@2.1.10`, `@rspack/dev-server@2.2.0`, and `@rspack/plugin-react-refresh@2.0.2`. Rspack offers a stable Webpack-like configuration/build model, non-experimental `output.module` in v2, built-in SWC TSX transformation, maintained React Fast Refresh integration, and fast development/build behavior.

It is not selected. The 2.x line is young, and its own plugin guidance acknowledges subtle compatibility differences despite broad Webpack API compatibility. Rspack documents React Router Data Mode examples, but it does not provide a ready project-specific custom SSR orchestration or a semantic request-route/module-to-browser-asset manifest. Adopting it would retain more project-owned development and manifest coordination without a demonstrated benefit for this accepted SSR model.

### Standalone Rolldown and esbuild

`rolldown@1.2.5` and `esbuild@0.28.2` were considered but are not selected. Standalone Rolldown supplies the bundler beneath Vite, but its application guidance recommends Vite for the complete dev-server, HMR, and production-build experience, and standalone HMR remains work in progress. esbuild provides fast browser/Node builds, watch/serve, TypeScript/JSX transformation, and metadata, but JavaScript HMR is explicitly outside its scope and code splitting retains documented limitations.

Selecting either directly would make the project owner of additional development, HMR, SSR, HTML transformation, and manifest orchestration without a demonstrated advantage. Neither becomes a future direct dependency through this ADR; Vite's own transitive implementation is governed later by the selected lockfile.

## Decision

This ADR establishes the following accepted M04 contract. Control Tower accepted M04 on 2026-08-22; M04-A1 records that decision and does not authorize implementation.

### Exact build-tool baseline

The complete future direct build-tool package set is exactly:

- `vite@8.2.2`
- `@vitejs/plugin-react@6.1.0`

Both must be exact-pinned under ADR 0001. They are not installed in M04. No `@react-router/dev`, React Router Framework Mode, direct Rolldown/esbuild package, separate minifier, legacy-browser plugin, or typecheck plugin is implied. The plugin's optional compiler-related peers and release feature are explicitly not selected.

### Logical build graph and boundaries

There is one shared **logical** route graph with stable route IDs and eagerly known matching fields. It feeds two separate production builds:

| Logical node | Allowed reachability | Production result |
| --- | --- | --- |
| Browser hydration entry | Browser-safe route definitions and implementations plus explicitly shared browser-safe modules | Hashed browser JavaScript, CSS, assets, and browser/SSR manifests |
| Node-compatible ESM server entry | Server route bindings, SSR-safe shared UI/route identity, and server-only application dependencies | One importable Node ESM server entry plus any server chunks |

The table defines capabilities, not filenames, directories, package boundaries, scripts, or repository layout. The browser and server builds are distinct build invocations over intentionally different reachability graphs. No assumption is made that future backend, worker, scheduler, ORM, native module, or migration code uses Vite or belongs to either graph.

Shared route identity does not mean every server route implementation is browser-importable. The browser graph may import only browser-safe code and modules explicitly designated as shared. Server-only modules, database clients, credentials, runtime secrets, private preview data, authorization internals, and privileged services must fail the browser build closed if directly or transitively reachable. The future implementation must provide an enforceable reachability guard and a negative fixture proving the build fails before emission; M05 decides its repository/package expression, not whether the guard exists.

Browser constants use an explicit public allowlist. `VITE_*`, any other `import.meta.env` exposure, and compile-time `define` replacement are public artifact inputs and never secret storage. Runtime secrets are read only by the future server/runtime boundary and must not be compiled into browser or server artifacts. An artifact scan must prove the absence of secret values and server-only module identifiers.

### Production artifact and manifest contract

The browser build emits, as one coherent build release:

- content-hashed browser JavaScript entry and split chunks;
- extracted CSS with build-determined ordering preserved and duplicate links removed by the consumer;
- imported static assets with content-addressed filenames;
- a Vite browser build manifest mapping logical entries/modules to emitted files, static imports, dynamic imports, CSS, and other imported assets; and
- a Vite SSR/module manifest capability mapping module IDs to associated browser files.

The server build emits an ESM server entry targeted to Node.js 24.19.0 and any ESM server chunks. A production server loads that built module directly; development-only module loading is not a production dependency. Actual Node.js import and runtime compatibility remain unverified validation debt.

Both manifests are build contracts. A consumer must reject a missing, malformed, internally inconsistent, or cross-release manifest instead of guessing filenames. Referenced artifacts must exist, remain inside the authorized logical output set, and use normalized relative artifact identifiers. CSS order must be consumed from build metadata and validated with representative shared and route-split styles; alphabetical or filesystem ordering is prohibited.

Each logical output set is clean before emission so stale chunks, maps, assets, or manifests cannot survive a build. Browser and server cleaning must be isolated so one build cannot erase the other's result. Build inputs must not inject the current time, random values, or absolute local/private paths. Given identical source, configuration, exact direct versions, lockfile, runtime, platform, and build inputs, emitted content, content-derived names, and manifest relationships are expected to remain stable. Bit-for-bit reproducibility across machines or time is not proved or claimed.

These artifacts do not decide a CDN, cache headers, public/provider paths, serving framework, immutable promotion, retention, rollback, or deployment layout. M11 owns CDN/media delivery, M12 owns application cache semantics, and M14 owns provider paths, shipping, promotion, and rollback.

### Code splitting and route-aware preload

Stable ECMAScript dynamic imports with statically analyzable specifiers are permitted. React Router `route.lazy` may split route implementation properties while stable route IDs and matching fields such as path/index/children remain eagerly known. No filesystem route convention, Framework Mode route module, lazy route discovery, unstable Router API, or project-wide manual chunk map is selected.

Automatic bundler splitting is the baseline; manual chunk assignment requires later measured evidence for a concrete problem and is not the default. Module federation and microfrontends are excluded.

The SSR manifest alone does not prove route-aware preload. Before request-specific JS or CSS preload is enabled, implementation must prove all of the following together:

1. the exact matched route IDs for the request are known;
2. the server render collects the exact build module IDs used by that request, including lazy route implementations;
3. those IDs map through the same-release manifest to complete JS, static-import, CSS, and asset dependencies;
4. traversal is cycle-safe, de-duplicated, deterministic, and preserves CSS order; and
5. direct requests, hydration, nested routes, errors, redirects, and lazy routes do not preload an unrelated private or authorization-sensitive module.

Until that executable proof exists, the manifests may support entry-level asset injection, but the project must not claim request-specific route-aware preload.

### Production modes and diagnostics

- Development uses an explicit development mode. Both production graphs use one explicit production mode; custom modes, if later needed, require a separate public-constant and secret-handling contract.
- The browser target is exactly Vite 8's versioned `baseline-widely-available` target fixed at 2026-01-01: Chrome 111, Edge 111, Firefox 114, Safari 16.4, and iOS 16.4. No legacy-browser plugin or separately selected polyfill package is added. Vite's built-in module-preload behavior may remain within the selected Vite baseline but does not broaden the browser support promise.
- Production browser JavaScript and CSS are minified with the selected Vite 8 defaults. Production server JavaScript is not minified so the Node ESM artifact remains debuggable rather than optimized for minimum size.
- Development client and server transforms must provide usable source mapping and corrected SSR stack locations.
- Production browser and server source maps are disabled until a private generation, access, retention, upload, and hosting policy is separately authorized. Inline and public production maps are prohibited.
- Mode values and public constants must be identical where shared semantics require them, explicitly typed/validated by future implementation, and included in the build input record. No runtime secret may be substituted into either graph.

### SSR dependency treatment

SSR dependencies are externalized by default. `ssr.noExternal`, forced bundling, or equivalent treatment is exceptional, scoped to one named dependency, documented with the exact reason, and allowed only after executable proof covers production build, Node ESM import, direct-document SSR, and the relevant package behavior. Broad forced bundling is not the baseline.

No compatibility assumption is made for an ORM, database client, native addon, backend framework, worker dependency, or conditional-export package. M05 decides dependency installation, the package manager, actual manifests, lockfile, package/runtime layout, and runtime packaging contract. M14 decides how server dependencies and built artifacts are shipped and promoted.

### Development model

Development uses Vite in middleware mode with `appType: "custom"` as a capability inside a project-owned development host. The host must:

- pass the direct-document HTML template through `transformIndexHtml` so Vite and React plugin transforms, the HMR client, and the React Refresh preamble are applied;
- load the logical server rendering entry through `ssrLoadModule` for development requests;
- exercise the same Data Mode direct-document SSR and browser hydration behavior required in production, including deep links and reloads;
- provide client HMR and React Fast Refresh through `@vitejs/plugin-react`;
- honor Vite server-module invalidation so a request after a relevant change cannot silently reuse a stale server module graph;
- fall back to an explicit full client reload or development-host recreation when a change cannot be safely applied, without prescribing a restart supervisor;
- report actionable browser transform/runtime failures and server SSR failures with source-mapped locations while sanitizing secrets and private data; and
- preserve a visible failure state instead of serving stale successful output after a transform or SSR error.

This capability contract selects no port, host, proxy, server framework, adapter, process count, restart supervisor, production server, container, or provider. `vite preview` is not a production SSR server and is not part of the production runtime contract.

### TypeScript contract

Vite transforms TypeScript/TSX; TypeScript typechecking is a separate required contract. A successful Vite client or SSR build does not prove type correctness. The accepted compiler remains exactly TypeScript 6.0.3.

Future implementation must run an independently defined typecheck over the applicable client, shared, server, and build-configuration types. M13 owns the typecheck/testing tools, commands, CI jobs, and enforcement policy. M04 adds no `vite-plugin-checker` or other typecheck plugin and selects no test runner or CI integration.

### Explicit exclusions

This decision does not select or add:

- `@react-router/dev`, React Router Framework Mode, a Framework Mode route-module convention, or a filesystem route convention;
- `@vitejs/plugin-react-swc`, deprecated `@vitejs/plugin-react-oxc`, React Compiler packages, or experimental compiler plugin options;
- the Vite Environment API as the mandatory integration baseline;
- React Server Components, streaming, deferred SSR, or pre-rendering;
- module federation, microfrontends, a legacy-browser plugin, or a direct Rolldown/esbuild dependency;
- a test runner, CI plugin, typecheck plugin, or CI job;
- application/build configuration, runtime source, manifests, lockfiles, generated artifacts, workflows, or infrastructure; or
- any server framework, production server, process topology, worker/backend bundler, provider, container, proxy, domain, environment topology, deployment, or promotion mechanism.

## Consequences

- If separately authorized, M05 receives an exact two-package build-tool baseline and a complete build contract without inheriting a package-manager or layout decision.
- The accepted Data Mode remains project-owned and independent of React Router Framework Mode.
- Separate browser and server builds, manifests, clean outputs, and an enforceable browser boundary become required implementation work.
- Development gains a documented SSR/HMR/Fast Refresh path, but the host integration and server invalidation behavior remain project responsibilities.
- Route-aware preload cannot be advertised from `ssrManifest` alone; it remains disabled until request-specific module collection and mapping are proved.
- Production source maps are initially unavailable, improving leakage control but increasing production-debugging cost until a private handling policy is authorized.
- Default SSR externalization reduces unnecessary bundling but transfers deployment of external server dependencies to the later packaging and deployment contracts.
- Vite's transformation speed does not remove the independent TypeScript typecheck obligation.
- Recent Vite 8/Rolldown internals and rolling documentation create upgrade and validation debt despite exact direct pins.

## Validation

M04 validates documentation and official evidence only. No package was installed, and no build, test, typecheck, development-server, SSR, hydration, or runtime command was run. Runtime compatibility of Node.js 24.19.0, TypeScript 6.0.3, React/DOM 19.2.8, React Router 8.3.0, Vite 8.2.2, and the React plugin 6.1.0 remains unverified.

Before any implementation can claim build or runtime compatibility, the responsible authorized milestones must provide executable evidence for:

- exact frozen installation from rechecked registry metadata and a committed lockfile;
- clean, separate production browser and server builds with no stale or cross-erased artifact;
- Node.js 24.19.0 import and execution of the built ESM server entry;
- manifest schema validation, same-release consistency, complete file existence, normalized identifiers, CSS order, and content-hashed browser assets;
- browser-reachability failure for a deliberate server-only import and scans showing no secret, credential, private preview value, database client, or server-only identifier in browser output;
- direct-request and reload SSR, hydration without mismatch or duplicate initial fetch, navigation, and error behavior in both development and production builds;
- client HMR, React Fast Refresh state behavior, server module invalidation, full-reload fallback, and actionable client/server errors;
- exact browser target behavior, client/server minification policy, development source mapping, and absence of production source maps;
- static dynamic imports and `route.lazy` across browser/server builds without losing eager stable route identity;
- request-specific route/module-ID collection and correct JS/CSS mapping before route-aware preload is enabled;
- default externalization and a separate executable proof for every forced-bundling exception;
- an independent TypeScript 6.0.3 typecheck; and
- repeated controlled builds before any stronger reproducibility claim is made.

M13 decides the validation tools and required CI jobs. Listing behaviors here creates obligations; it does not authorize tools, commands, workflows, or status checks.

## Risks

- Exact engine and peer ranges may overstate real compatibility; no selected package has been installed or executed together.
- Vite 8 and its Rolldown architecture are recent, so exact pins reduce drift but do not remove integration or regression risk.
- Low-level custom SSR is intentionally project-owned. Incorrect HTML transformation, module invalidation, manifest consumption, or production loading can break direct requests or hydration.
- A logical shared route graph can accidentally create browser reachability to server-only code unless the future fail-closed guard and negative proof are effective.
- Split-route CSS can render in the wrong cascade order if a consumer guesses ordering or incompletely traverses manifest relationships.
- Route-aware preload can become incomplete, overbroad, or privacy-sensitive without exact request-used module collection.
- Externalized packages may behave differently under Node ESM conditional exports or require deployment assets/native binaries not represented by the server build.
- Disabled production source maps make incidents harder to debug until M14 authorizes a private handling and hosting policy.
- Rolling Vite, React Router, Webpack, Rspack, Rolldown, and esbuild documentation can change after the cutoff. Exact package metadata and tagged sources must be rechecked before installation or update.
- Bit-for-bit reproducibility, artifact promotion, cache headers, CDN behavior, and production packaging remain unproved and deliberately deferred.

## Follow-ups

- Control Tower accepted M04 on 2026-08-22 after the Independent Reviewer returned Accepted with P0/P1/P2 = 0/0/0; runtime compatibility remains unverified.
- M04-A1 only records that decision in this ADR, architecture, and roadmap. It does not revisit technical content, authorize implementation or M05, or prove runtime compatibility.
- M05 must recheck exact package metadata and decide dependency installation, the package manager, actual manifest and lockfile contract, repository/package/runtime layout, version carriers, and runtime packaging under its own task contract.
- M06 must choose the backend/server framework and React Router adapter and decide the concrete Web `Request` to `Response`, HTTP, header, and error-boundary integration without changing the build contract implicitly.
- M11 and M12 retain CDN/media and application cache decisions.
- M13 must choose typecheck, test, and CI enforcement tools/jobs and cover the validation obligations above.
- M14 must choose production server/dependency shipping, artifact locations, provider/container/process/environment topology, private source-map handling, promotion, rollback, backup, and restore.
- A move to Framework Mode, the Environment API baseline, streaming, pre-rendering, RSC, manual chunking, a legacy browser path, or another bundler requires separately authorized evidence and, where it changes an accepted decision, a superseding ADR.
- M05-M14 remain Planned and unauthorized until separately activated by Control Tower.

## Supersedes / Superseded by

None.
