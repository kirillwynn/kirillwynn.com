# Architecture

## Current state

No application architecture is implemented. This repository currently defines governance, product requirements, logical boundaries, five Accepted ADRs, and a remaining ADR backlog only.

## Hard constraints

- The system is a greenfield implementation. Legacy code and data formats are not inputs to the new architecture, and no old data migration is planned.
- Secrets and real environment values remain outside Git.
- Staging and production must be isolated. Existing legacy staging remains untouched.
- Public content and preview or private content must remain separated across data access and delivery paths.
- A custom emoji production import is fail-closed until provenance and licensing are approved separately.
- Release design must support staging-first immutable promotion, backup, and verified restore.

## Logical system context

These are logical components and flows, not claims about services, processes, repositories, or deployment units:

```text
Browser / public web -> application / API boundary -> PostgreSQL
Author -> first-party admin + Tiptap editor -> content / revisions / publication lifecycle
Worker -> scheduling + durable email outbox
Application / worker -> object storage / CDN
Application / worker -> replaceable email provider
Application -> Google / GitHub identity providers
```

## Trust and data boundaries

- **Browser:** untrusted input and public output; authorization cannot rely on UI state.
- **Admin:** a privileged first-party interface; server-side authorization still governs every operation.
- **Application/API boundary:** validates input, authenticates identity, enforces authorization and publication visibility, and coordinates persistence.
- **PostgreSQL:** durable application state behind the server boundary; direct browser access is prohibited.
- **Worker:** performs authorized asynchronous and scheduled work with durable, idempotent state transitions.
- **Object storage/CDN:** stores and delivers media while preserving the public-versus-private boundary.
- **OAuth providers:** external identity systems; request minimal scopes and distrust provider input until validated.
- **Email provider:** replaceable external delivery boundary; durable intent and deduplication remain under application control.

## Preferred direction — pending ADR

The preferred technology direction is React 19, TypeScript, React Router 8, Gravity UI, TanStack Query, Tiptap, PostgreSQL, and TypeScript/Node.js backend and worker code. This list is not an accepted architecture decision and does not establish exact versions, compatibility, packaging, framework, or runtime topology.

No decision has yet established same-origin deployment, process count, cloud or vendor.

[ADR 0001](decisions/0001-version-baseline-and-update-policy.md) accepts only exact starting versions, the published metadata compatibility envelope, and the pin/update policy. It installs nothing and does not prove runtime compatibility. It does not choose a package manager, repository or runtime topology, React Router mode, a bundler, backend/API, or deployment.

[ADR 0002](decisions/0002-react-router-ssr-runtime-deployment-model.md) accepts React Router 8.3.0 Data Mode with runtime initial-document SSR, buffered rendering as the baseline, hydrated client navigation, a portable Web `Request` to `Response` boundary, and a fullstack SSR-capable hosting class. Runtime compatibility remains unverified. The repository and runtime topology, backend adapter, and hosting provider remain open.

[ADR 0003](decisions/0003-bundler-build-development-model.md) accepts exactly Vite 8.2.2 with `@vitejs/plugin-react` 6.1.0, separate browser and Node ESM builds, browser and SSR manifests, middleware-mode development with React Fast Refresh, and a fail-closed browser boundary. Runtime compatibility remains unverified. Package, repository, and runtime topology, backend, testing/CI, and deployment remain open.

[ADR 0004](decisions/0004-repository-package-runtime-topology.md) accepts pnpm 11.22.0 through Corepack 0.35.0, one private workspace with explicit shared, web, server, and future-worker package ownership, one lockfile, strict dependency boundaries, and explicit production dependency closure. It implements nothing and does not prove package, build, SSR, hydration, worker, or runtime compatibility; process and deployment topology remain open.

[ADR 0005](decisions/0005-backend-api-framework-and-contracts.md) accepts exactly `hono@4.13.3` with no Node adapter, a project-owned strict Node/Web bridge, a reserved `/api/v1` namespace with RFC 9457 problem contracts, bounded resource limits, and one Vite-owned development HMR `upgrade` listener on the shared project-owned server. It implements nothing, installs no dependency, and does not prove typecheck, build, SSR, HTTP, security, or runtime compatibility; ORM/migrations, identity, editor, worker, media, search, testing/CI, and deployment remain open.

## Remaining ADR backlog

Focused ADRs, based on current official primary sources at decision time, must decide:

1. ORM and migration system;
2. session, authentication, OAuth, and CSRF architecture;
3. Tiptap document schema, versioning, and sanitization;
4. worker, scheduler, and durable outbox architecture;
5. search architecture;
6. storage, CDN, and media architecture;
7. testing and CI strategy; and
8. deployment, isolation, backup, restore, and rollout model.
