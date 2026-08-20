# Roadmap

## Planning model

This roadmap uses rolling-wave planning: near-term milestones receive precise task contracts, while later phases remain directional until the Control Tower authorizes them. Listing work here does not commit scope, architecture, dates, or external changes.

Rows labeled `Mxx`, `M02+`, or `Gxx`, including combined labels, are directional phase containers only. A container is not an executable milestone and cannot be handed to a Builder or authorized as one task. Before authorization, the Control Tower decomposes the next slice into the smallest independently verifiable milestones. Each executable milestone has one testable outcome and its own task contract, worktree, Builder, commit, and Reviewer. A defect found after review becomes a separately authorized additive remediation milestone, never a history rewrite.

## Current milestones

| Phase | Status | Directional scope |
| --- | --- | --- |
| M01 | Remediation required | Repository Foundation. |
| M01-R1 | Review pending | Repository Foundation Governance Remediation. |

Neither milestone is Accepted. Final acceptance belongs to the Control Tower after independent review.

## Planned ADR milestones

Each row below is a separate planned milestone. Listing it is not authorization.

| Milestone | Status | Testable outcome |
| --- | --- | --- |
| M02 | Planned | Decide exact stable versions, compatibility, and pin/update policy. |
| M03 | Planned | Decide the React Router SSR, runtime, and deployment model. |
| M04 | Planned | Decide the bundler, build, and development model. |
| M05 | Planned | Decide the backend/API framework and API/error contracts. |
| M06 | Planned | Decide the ORM, PostgreSQL migrations, and schema compatibility. |
| M07 | Planned | Decide the sessions, email/password, OAuth, and CSRF architecture. |
| M08 | Planned | Decide Tiptap schema, versioning, sanitization, and renderer compatibility. |
| M09 | Planned | Decide the worker, scheduler, durable outbox, and idempotency model. |
| M10 | Planned | Decide object storage, CDN, and media processing. |
| M11 | Planned | Decide search, ranking, pagination, and cache model. |
| M12 | Planned | Decide the testing strategy and required CI jobs. |
| M13 | Planned | Decide deployment topology, environment isolation, promotion, rollback, backup, and restore. |

## Directional phase containers

These remaining directions are non-authorizable containers until the Control Tower decomposes them into executable milestones.

| Container | Status | Directional scope |
| --- | --- | --- |
| Mxx | Planned | Workspace/runtime foundation and baseline CI. |
| Gxx | Planned | Separate governance gate for required pull requests and required checks. |
| Mxx | Planned | Theme, public shell, and Bridge. |
| Mxx | Planned | Identity, email authentication, OAuth, nickname, and admin foundation. |
| Mxx | Planned | Post lifecycle, Tiptap blocks, media, revisions, preview, publish, scheduling, and unpublish. |
| Mxx | Planned | Public post, Feed SSR, infinite loading, search, state restoration, and SEO. |
| Mxx | Planned | Comments, flat threads, responsive UX, and moderation. |
| Mxx/Gxx | Planned | Empty custom catalog and reaction API/UI; separate provenance gate; approved corpus import only after the gate. |
| Mxx | Planned | Double opt-in, unsubscribe, outbox, provider worker, and webhooks. |
| Mxx | Planned | Security, observability, immutable builds, backup/restore, and rollout. |
| Mxx | Planned | Separate reader, author, identity, discussion, and subscription end-to-end milestones. |
| Mxx | Planned | Accessibility, performance, security/license, and release audits. |
| Gxx/Mxx | Planned | Separately authorized isolated staging, staging acceptance, production readiness, and production promotion. Legacy staging remains unchanged. A separate Release Operator participates only at an agreed checkpoint after explicit Control Tower authorization for that checkpoint; this grants no authority for other external mutations. |
| Mxx | Planned | Finance only after an accepted, working non-finance production release. |

M01 requires remediation, and M01-R1 awaits review. M02-M13 and all directional containers remain planned and unauthorized.
