# Roadmap

## Planning model

This roadmap uses rolling-wave planning: near-term milestones receive precise task contracts, while later phases remain directional until the Control Tower authorizes them. Listing work here does not commit scope, architecture, dates, or external changes.

Every Mxx milestone moves through Builder, independent Reviewer, and explicit acceptance. A defect in a handed-off commit is fixed by a separately authorized additive remediation milestone, never by history rewriting. Governance G-gates require separate authorization and are not ordinary Builder commits.

## Ordered phases

| Phase | Status | Directional scope |
| --- | --- | --- |
| M01 | Review pending | Repository Foundation. |
| M02+ | Planned | ADRs for versions and compatibility; React Router runtime; bundler; backend/API; ORM and migrations; authentication; Tiptap schema; jobs and outbox; storage; search; testing and CI; deployment. |
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
| Gxx/Mxx | Planned | Separately authorized isolated staging, staging acceptance, production readiness, and production promotion. |
| Mxx | Planned | Finance only after an accepted, working non-finance production release. |

Only M01 is currently in review. Every later phase is planned and requires its own authorized contract.
