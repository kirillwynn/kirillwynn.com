# Architecture

## Current state

No application architecture is implemented. This repository currently defines governance, product requirements, logical boundaries, and an ADR backlog only.

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

## Required ADR backlog

Focused ADRs, based on current official primary sources at decision time, must decide:

1. exact stable versions and compatibility;
2. React Router SSR, runtime, and deployment model;
3. Webpack 5, Vite, or another bundler;
4. repository, package, and runtime topology;
5. backend and API framework;
6. ORM and migration system;
7. session, authentication, OAuth, and CSRF architecture;
8. Tiptap document schema, versioning, and sanitization;
9. worker, scheduler, and durable outbox architecture;
10. search architecture;
11. storage, CDN, and media architecture;
12. testing and CI strategy; and
13. deployment, isolation, backup, restore, and rollout model.
