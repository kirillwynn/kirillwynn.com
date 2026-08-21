# Architecture

## Current state

No application architecture is implemented. This repository currently defines governance, product requirements, logical boundaries, one Accepted version-baseline ADR, and a remaining ADR backlog only.

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

No decision has yet established same-origin deployment, monorepo layout, process count, cloud or vendor, bundler, or backend framework.

[ADR 0001](decisions/0001-version-baseline-and-update-policy.md) accepts only exact starting versions, the published metadata compatibility envelope, and the pin/update policy. It installs nothing and does not prove runtime compatibility. It does not choose a package manager, repository or runtime topology, React Router mode, a bundler, backend/API, or deployment.

## Remaining ADR backlog

Focused ADRs, based on current official primary sources at decision time, must decide:

1. React Router SSR, runtime, and deployment model;
2. Webpack 5, Vite, or another bundler;
3. repository, package, and runtime topology;
4. backend and API framework;
5. ORM and migration system;
6. session, authentication, OAuth, and CSRF architecture;
7. Tiptap document schema, versioning, and sanitization;
8. worker, scheduler, and durable outbox architecture;
9. search architecture;
10. storage, CDN, and media architecture;
11. testing and CI strategy; and
12. deployment, isolation, backup, restore, and rollout model.
