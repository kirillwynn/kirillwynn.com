# 0002: React Router SSR, Runtime, and Deployment Model

- **Status:** Proposed
- **Date:** 2026-08-21
- **Owners:** Control Tower

## Context

[ADR 0001](0001-version-baseline-and-update-policy.md) accepts Node.js 24.19.0 LTS, React and React DOM 19.2.8, and `react-router` 8.3.0 as an exact metadata-compatible baseline. It does not select a React Router mode, prove SSR or hydration, choose a bundler or server framework, or establish a deployment model. This ADR proposes the application-facing router, initial-document, request/data, runtime, and hosting-capability contracts needed before those implementation choices. It does not make the proposal effective: M03 remains Review pending until independent review and an explicit Control Tower decision.

The product requires an SSR first page for Feed, SEO-capable post documents with canonical and Open Graph metadata, correct deep links and reloads, and hydrated client navigation. It also requires infinite Feed pagination, live search, comments, reactions, auth-sensitive account and admin surfaces, and strict separation of public data from preview or private data. The architecture keeps a Node.js backend direction and TanStack Query for interactive server-state caching while rejecting the legacy implementation.

Official evidence was checked at **2026-08-21T11:22:56Z**. Evidence tied to an exact published version is treated separately from documentation that can change after this cutoff:

- **Version-specific evidence:** the official [`react-router@8.3.0` release](https://github.com/remix-run/react-router/releases/tag/react-router%408.3.0) and exact npm registry metadata for [`react-router@8.3.0`](https://registry.npmjs.org/react-router/8.3.0), [`@react-router/dev@8.3.0`](https://registry.npmjs.org/%40react-router%2Fdev/8.3.0), [`@react-router/node@8.3.0`](https://registry.npmjs.org/%40react-router%2Fnode/8.3.0), [`@react-router/express@8.3.0`](https://registry.npmjs.org/%40react-router%2Fexpress/8.3.0), and [`@react-router/serve@8.3.0`](https://registry.npmjs.org/%40react-router%2Fserve/8.3.0).
- **Rolling documentation at the cutoff:** the official guidance for [router modes](https://reactrouter.com/start/modes), [custom Data Mode integration](https://reactrouter.com/start/data/custom), [rendering strategies](https://reactrouter.com/start/framework/rendering), [SPA mode](https://reactrouter.com/how-to/spa), [pre-rendering](https://reactrouter.com/how-to/pre-rendering), [deployment](https://reactrouter.com/start/framework/deploying), and the [framework quick start](https://reactrouter.com/tutorials/quickstart). These pages are evidence and examples, not permission to adopt their sample tools, packages, server, database, container, or provider choices.

The exact package metadata establishes an ESM package with a Node.js engine range of `>=22.22.0`; Node.js 24.19.0 is inside that published range. This is metadata compatibility only. No install, server import, production build, SSR, hydration, or runtime compatibility has been demonstrated.

## Decision drivers

- Render every supported document route correctly on a direct request or reload, including Feed and SEO-critical post pages.
- Hydrate the exact server result and use client navigation afterward without duplicating the initial data request.
- Use route loaders, actions, pending states, redirects, status codes, and route error boundaries without surrendering the still-open bundler and server abstractions.
- Keep preview, private, authenticated, and public data separated at both serialization and cache boundaries.
- Give React Router and TanStack Query distinct, testable data and revalidation ownership.
- Preserve M04 as the bundler/build decision, M05 as the package/repository/runtime-topology decision, M06 as the backend/API/server-adapter decision, and M14 as the provider/deployment-topology decision.
- Stay within the exact package baseline and update policy of ADR 0001 without adding a manifest or dependency.
- Exclude experimental Router APIs from the v1 production contract.

## Considered options

1. **Data Mode with a project-owned SSR integration.** Data Mode provides loaders, actions, pending states, fetchers, and error boundaries while retaining control over bundling, data, and server abstractions. The official [mode guidance](https://reactrouter.com/start/modes) and [custom integration guide](https://reactrouter.com/start/data/custom) explicitly support this separation. This is the proposed option.
2. **Framework Mode with the official Vite integration.** Framework Mode wraps Data Mode with the React Router Vite plugin, according to the official [mode guidance](https://reactrouter.com/start/modes). In the exact [`@react-router/dev@8.3.0` metadata](https://registry.npmjs.org/%40react-router%2Fdev/8.3.0), Vite `^7.0.0 || ^8.0.0` is a non-optional peer dependency. Selecting Framework Mode here would therefore decide Vite before M04. It is not proposed.
3. **Declarative Mode with project-built data and SSR abstractions.** Declarative Mode supplies basic matching and navigation, while Data Mode adds loaders, actions, pending states, and related route data APIs, as the [mode comparison](https://reactrouter.com/start/modes) documents. Rebuilding those capabilities beside Declarative Mode would duplicate the contract the project needs. It is not proposed.
4. **SPA or static-only production deployment.** The official [SPA guide](https://reactrouter.com/how-to/spa) describes disabling runtime SSR, and the [rendering](https://reactrouter.com/start/framework/rendering) and [pre-rendering](https://reactrouter.com/how-to/pre-rendering) guides distinguish runtime SSR from build-time output. A static-only initial document cannot satisfy the required runtime Feed, auth-sensitive documents, and direct-request behavior. It is not proposed.
5. **Experimental React Server Components path.** The current official [API navigation labels the RSC APIs as unstable](https://reactrouter.com/start/modes). RSC would introduce an unstable application and build contract before the standard SSR path is validated. It is not proposed for v1.

## Decision

This ADR proposes the following v1 contract. It remains a proposal until Control Tower acceptance; no runtime capability is claimed by this documentation-only milestone.

### Router mode

- Use React Router 8.3.0 **Data Mode**.
- In the browser, construct the router with `createBrowserRouter` and render it with `RouterProvider`.
- On the server, use `createStaticHandler`, `createStaticRouter`, and `StaticRouterProvider`. The official [custom Data Mode guide](https://reactrouter.com/start/data/custom) documents these browser and server APIs, a shared route-object model, Web Fetch requests, raw `Response` passthrough, status and header production, and hydration data.
- The server and browser use the same logical route graph, stable route identities, and compatible hydration state. How a future build partitions route implementation code while preserving that graph remains an M04 and M06 implementation decision.
- `react-router/dom` is the `./dom` subpath export of `react-router`, as shown by the exact [`react-router@8.3.0` exports metadata](https://registry.npmjs.org/react-router/8.3.0); it is not a separate dependency.
- Framework Mode is not selected because its official Vite integration and mandatory Vite peer would prematurely select the M04 bundler. A later Vite choice does not automatically change the router mode. Moving to Framework Mode requires a separate superseding ADR.
- Declarative Mode is not selected because the project requires route loaders and actions, pending states, redirects, and route error boundaries supplied by Data Mode.
- RSC APIs and every React Router API or flag marked unstable or experimental are prohibited for v1.

### Rendering model

- Runtime SSR is mandatory for the initial document. Every supported document route must produce correct output on a direct request and reload; this includes route status, headers, SEO-critical data, canonical metadata, Open Graph metadata, and access-sensitive behavior where applicable.
- The browser hydrates the exact server-rendered state and then uses client navigation, including back and forward navigation. It must not repeat the initial loader fetch solely because hydration began.
- SPA-only and static-only hosting are not production models. The official [deployment guide](https://reactrouter.com/start/framework/deploying) distinguishes fullstack from static hosting, while the [SPA guide](https://reactrouter.com/how-to/spa) states that SPA mode disables runtime server rendering.
- Build-time pre-rendering is not enabled. The official [pre-rendering guide](https://reactrouter.com/how-to/pre-rendering) defines it as rendering pages at build time; route selection and build-time data access would add decisions not authorized here.
- Buffered SSR is the initial baseline. Streaming, deferred or promise-valued loader data, and selective pre-rendering are deferred optimizations. None may be enabled without separate justification and validation of status/header timing, errors, aborts, hydration, security, caching, and hosting support.
- Runtime SSR and hydration remain validation debt. This ADR does not state that either already works with the accepted versions or a future production build.

### Request and response contract

The future SSR boundary must satisfy this application-facing sequence without selecting a concrete server framework or adapter:

1. Receive a Web Fetch `Request`. A future adapter may translate native server input into that standard request, but the application boundary itself is Web Fetch based.
2. Execute `createStaticHandler(routes).query(request)` against the server representation of the shared logical route graph.
3. If `query` returns a `Response`, return it immediately with its status, headers, and body semantics intact. This includes redirects and route responses; it must not be converted into an HTML success response.
4. Otherwise, create the static router from the returned context and the handler's data routes.
5. Render the document with `StaticRouterProvider` using buffered SSR, then produce an HTML `Response` with the context's correct status and the applicable route and document headers. Header composition must preserve HTTP semantics and be explicitly tested rather than inferred from a server framework.
6. Expose only the serialized hydration data required by the browser. Serialization must be safe for an HTML script context and must exclude secrets, private preview data not intended for that viewer, internal diagnostics, and server-only values.
7. Initialize `createBrowserRouter` with the same logical route graph and that hydration state, then hydrate with `RouterProvider`. The official [custom integration sequence](https://reactrouter.com/start/data/custom) demonstrates `hydrationData` and the `react-router/dom` provider subpath.
8. Carry cancellation through the original `request.signal` into loader/action I/O and stop obsolete work when the request or navigation is aborted.
9. Support GET and HEAD document requests, redirects, expected route responses, 404s, and sanitized unexpected 500 boundaries. HEAD must retain the corresponding GET status and headers without sending a response body.
10. Keep secrets, database clients, private preview payloads, authorization internals, and other server-only implementation out of emitted HTML, hydration data, and browser artifacts.

The official [custom Data Mode SSR guide](https://reactrouter.com/start/data/custom) is evidence that this `Request`/`Response` and static-router contract can be expressed with project-owned bundler and server abstractions. It is not an implementation template and does not choose the future adapter, handler shape, header-merging policy, or server framework.

### Route and data ownership

- React Router loaders own document-level bootstrap data, session/viewer bootstrap, route status, redirects, and SEO-critical initial data needed to render the requested document correctly.
- TanStack Query owns infinite pagination, live search, comments, reactions, and the long-lived interactive client cache after the document bootstrap.
- Each resource must have one canonical revalidation owner. Router automatic revalidation and TanStack Query invalidation must not both own a resource unless a later explicit resource contract defines the handoff, deduplication, and invalidation rules.
- Route modules orchestrate requests and presentation-level route behavior; they do not contain domain/business persistence logic.
- Route definitions or modules imported by a browser build must not directly or transitively import secrets, database clients, privileged service credentials, or server-only modules. Server-only loader bindings must remain outside browser-reachable imports while preserving the same logical route graph.
- Route actions are technically available in Data Mode, but this ADR adopts no mutation architecture. Mutation transport, API and error formats, authorization, session behavior, cookies, and CSRF remain M06 and M08 decisions.
- Public, authenticated, and preview/private responses must remain isolated. Neither Router data nor TanStack Query state may cross viewer, authorization, preview, or request cache boundaries.

### Runtime and deployment class

- Target a Node.js 24.19.0-compatible runtime class and ESM server modules. The exact [`react-router@8.3.0` metadata](https://registry.npmjs.org/react-router/8.3.0) publishes `type: module` and Node `>=22.22.0`; satisfying that range is not proof of production compatibility.
- Require fullstack, runtime-SSR-capable hosting. Static hosting alone is insufficient.
- Preserve a portable Web `Request` to `Response` application boundary so M06 can choose the server framework and adapter without changing route semantics.
- Require a future production build to emit a logical server entry or handler and browser assets. Their filenames, directories, bundler, chunking, workspace ownership, and serving mechanism are not decided. The official [quick start](https://reactrouter.com/tutorials/quickstart) is evidence that server-handler and browser-asset outputs are a supported deployment shape, but its Vite, Express, `@react-router/serve`, Docker, and template examples are not selected.
- Select no provider preset and no hosting vendor. This ADR does not decide process count, service split, ports, reverse proxy, containers, domains, environments, rollout, backups, or deployment topology.

### Package boundary

- For this Data Mode proposal, the only direct React Router package remains the ADR 0001 baseline `react-router@8.3.0`. This statement is a package contract, not a manifest addition.
- `react-router/dom` remains a package subpath, not a package.
- This ADR does not select `@react-router/dev`, `@react-router/node`, `@react-router/serve`, or `@react-router/express`. Their exact [dev](https://registry.npmjs.org/%40react-router%2Fdev/8.3.0), [Node](https://registry.npmjs.org/%40react-router%2Fnode/8.3.0), [serve](https://registry.npmjs.org/%40react-router%2Fserve/8.3.0), and [Express](https://registry.npmjs.org/%40react-router%2Fexpress/8.3.0) metadata is evidence about available integration packages, not a package selection.
- M06 retains the server framework and adapter-package decision. M05 retains the package manager, actual manifest, lockfile, workspace layout, and repository/runtime topology decisions.
- If a later ADR selects any direct `@react-router/*` package, ADR 0001 requires it to be exact-pinned and updated atomically with `react-router`.

### Explicit non-decisions

| Milestone | Decision deliberately left open |
| --- | --- |
| M04 | Bundler, build pipeline, development server, code splitting, and production artifact implementation. No Vite, Webpack, Rollup, Rolldown, or alternative is selected. |
| M05 | Package manager, manifest and lockfile, workspace/repository layout, version carriers, package boundaries, and runtime/process topology. |
| M06 | Backend/server framework, React Router server adapter, API and error format, mutation transport, authorization enforcement integration, and server header-composition implementation. |
| M08 | Sessions, email/password, OAuth, cookies, and CSRF architecture. |
| M12 | Search, ranking, pagination, detailed cache keys and lifetimes, and per-resource Router/TanStack revalidation contracts. |
| M13 | Test framework, browser/runtime test tooling, CI jobs, and required status checks. |
| M14 | Hosting provider, cloud or VPS, containers, proxy, domains, service/process split, environments, promotion, rollback, backup, restore, and rollout topology. |

M07, M09, M10, and M11 also remain Planned and unchanged in [the roadmap](../roadmap.md). This proposal defines no database/ORM, editor schema, job system, or media/storage decision, and it defines no route tree or URL taxonomy.

## Consequences

- Feed and post documents receive a clear runtime-SSR and hydration target without forcing the build or backend implementation.
- Route-aware status, redirects, error boundaries, and SEO bootstrap data have one initial-document owner.
- Interactive collections and mutations can use TanStack Query without making it a second owner of Router bootstrap revalidation.
- M04 must produce a safe server/browser partition for one logical route graph, and M06 must adapt a concrete server to the portable Web boundary.
- Fullstack hosting becomes a required capability, while provider and topology choices remain open.
- The project must carry explicit SSR, hydration, serialization, abort, cache-isolation, and artifact-leakage validation debt before claiming runtime compatibility.
- A move to Framework Mode is intentionally more expensive: it requires evidence, a superseding ADR, and review of the Vite/tooling coupling rather than following automatically from any later bundler choice.

## Validation

This is documentation-only validation. No dependency was installed and no build, typecheck, test, server, SSR, hydration, or runtime command was run. Before installation, the responsible milestone must recheck exact registry metadata. After M05 selects a package manager, the first dependency-bearing implementation must perform a frozen install.

The responsible implementation milestones must add and pass all of the following before runtime compatibility can be claimed:

- production server and browser build compatibility;
- an ESM server-entry import smoke on exact Node.js 24.19.0;
- GET and HEAD document SSR, including deep links and reloads;
- redirect, status, header, and expected raw `Response` passthrough;
- correct 404 behavior and sanitized unexpected 500 handling;
- route-level expected and unexpected error boundaries;
- hydration without mismatch or a duplicate initial fetch;
- browser navigation plus back/forward state behavior after hydration;
- loader and action abort propagation through `request.signal`;
- safe, deterministic hydration-data serialization for an HTML script context;
- proof that secrets and server-only code are absent from browser artifacts and emitted HTML;
- per-resource Router/TanStack ownership and revalidation tests;
- cache isolation among anonymous, authenticated, and preview/private responses;
- streaming and pre-render tests before either feature can be proposed for enablement; and
- a source and artifact scan proving that no RSC or other unstable React Router API or flag is used.

M13 retains ownership of the testing and CI strategy; listing required behaviors here does not choose tools or jobs.

## Risks

- Package metadata and a documented API shape can still fail in the final production build. Engine compatibility is not runtime proof; the validation debt remains blocking for implementation acceptance.
- A future bundler may make it difficult to share route identity without exposing server-only imports. M04 must demonstrate the partition and artifact scans before application code relies on it.
- Hydration payloads can leak private data or create injection vulnerabilities. Loader return contracts, serialization, viewer scoping, and cache isolation require explicit tests.
- Router revalidation and TanStack invalidation can produce duplicate requests, races, or stale state. One canonical owner per resource and M12 resource contracts control this risk.
- Redirects, thrown responses, HEAD handling, and nested route errors can lose status or headers at an adapter boundary. M06 must preserve the portable response semantics and the implementation tests must cover them.
- Buffered SSR can increase time to first byte for slow routes. Streaming remains disabled until its more complex timing, error, security, and hosting behavior is separately justified and validated.
- Rolling React Router documentation may change after the evidence cutoff. Exact metadata must be rechecked before installation, and any material contract change requires review and potentially a superseding ADR.

## Follow-ups

- Independent review must verify this proposal. Only Control Tower may decide whether to accept it; until then M03 remains Review pending and this ADR remains Proposed.
- A separately authorized M03-A1 may record acceptance and update architecture only after that decision. This Builder does not edit architecture.
- M04 must decide the bundler/build/development model and prove safe server/browser route partitioning without changing this mode automatically.
- M05 must decide repository/package/runtime topology, package manager, manifests, lockfile, workspace layout, and version carriers.
- M06 must decide the backend/API/server framework, adapter package, error contracts, mutation transport, and status/header integration.
- M08 must decide sessions, OAuth, cookies, authorization integration, and CSRF.
- M12 must decide search, pagination, cache behavior, and explicit per-resource revalidation ownership.
- M13 must decide the test and CI strategy and implement the required validation coverage.
- M14 must decide provider, deployment, environment, rollout, backup, and restore topology while preserving runtime SSR and the Web boundary.
- Streaming, deferred or promise-valued loader data, selective pre-rendering, Framework Mode, RSC, and any unstable API each require separately authorized evidence and decision work before use.

## Supersedes / Superseded by

None.
