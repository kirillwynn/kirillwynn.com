# Testing and security verification

Status: Milestone 11 coverage audit

Last updated: 2026-07-28

## Coverage matrix before Milestone 11 changes

The baseline at `d071f1d84b990414da73806b842c871912209c98` collects 480
backend cases, 152 Vitest cases, and 131 infrastructure pytest cases, in
addition to the Docker Compose smoke script. The matrix below was completed
before adding Milestone 11 scenarios so that the new suite does not repeat
behavior already proved by a narrower test.

| Area | Existing proof | Baseline disposition | Milestone 11 gap |
| --- | --- | --- | --- |
| Posts and content models | `tests/blog/test_models.py`, `test_blocks.py`, `test_editorial.py` | Covered: hierarchy, constraints, 13 block types, revisions, scheduling, rollback | Add upload type/size and metadata handling |
| Public content API | `tests/blog/test_api.py`, `test_search.py` | Covered: anonymous/read-only access, exact contracts, pagination, Unicode slugs, visibility, restrictions, preview isolation, search/tags and PostgreSQL ranking | Make PostgreSQL ranking an explicit no-skip CI gate |
| Comments and threads | `tests/discussions/test_api.py`, `test_models.py` | Covered: one-depth threads, owner mutations, plain text/XSS boundary, tombstones, hidden content, stable cursors, anonymous/inactive/banned behavior and `Retry-After` | Add site-author boundary, surrogate/noncharacter rejection and concurrent create-limit proof |
| Reactions | `tests/discussions/test_reactions.py`, `test_postgresql_concurrency.py` | Covered: normalized Unicode emoji, surrogate rejection, visibility/tombstones, auth/CSRF, participants cursor, rate limit and parallel toggles | Include the PostgreSQL cases in the explicit no-skip gate |
| Authentication and sessions | `tests/test_auth.py`, `test_session_api.py`, `test_settings.py` | Covered: Google/GitHub mock callbacks, linking, banned/inactive users, malicious return-to matrix, logout CSRF and hardened cookies | Add expired-session and cross-session/cross-origin CSRF negatives |
| Subscriptions and email | `tests/subscriptions/` | Covered: double opt-in, confirmation, unsubscribe, webhook verification, enumeration resistance, hashed rate limits, durable/idempotent outbox, retries and parallel claims | Exercise the complete browser flow in Playwright; include concurrency in no-skip gate |
| Browser presentation | `frontend/next/tests/` | Covered: SSR contracts, escaping, Draft Mode, comments, threads, reactions, auth, subscriptions, keyboard/Escape/focus restoration and exact proxy rewrites | Add real-browser reader, mock login, discussion, subscription, preview and feed flows at all required viewports |
| Browser secret boundary | `security-boundary.test.ts`, CI static scan, `verify-next-runtime-origins.mjs` | Covered: no `NEXT_PUBLIC` secrets, no broad `/api/*` rewrite, no internal Django origin or sentinel secrets in static assets | Scan browser bundles, traces, screenshots and other retained test artifacts with one shared denylist |
| Nginx and routing | `infra/tests/test_nginx_routes.py`, `nginx_config_test.sh`, `container_smoke.sh` | Covered: exact frontend API exceptions, Django routes, headers, dynamic DNS, bounded missing upstream and restart | Keep the full Compose suite mandatory and preserve exact-route assertions |
| Backup and recovery | `test_release_scripts.py`, `test_rollout_state_machine.py`, `container_smoke.sh` | Covered: metadata/checksum rejection, populated scratch restore, bootstrap/recovery/rollback faults and state lineage | Make the full Compose rehearsal an explicit required CI job |
| S3/MinIO and worker egress | Compose isolation tests and `container_smoke.sh` | Covered: isolated networks, MinIO upload/read URL, missing-media 404, role-scoped secrets and worker-only provider egress | Add retained-image metadata scan |
| Security headers | production settings tests, Nginx header snippet and config tests | Covered: secure host-only cookies, HSTS, CSP, frame, referrer and content-type headers | Add a live Compose header assertion without weakening policy |

## Milestone 11 additions

Backend additions:

- metadata-stripping Wagtail image uploads with explicit JPEG/PNG/WebP,
  eight-MiB, and 40-megapixel limits;
- PDF-only, ten-MiB document uploads;
- extension/content mismatch, image and document size, EXIF/metadata, surrogate
  and Unicode noncharacter negatives;
- cross-session CSRF tokens, cross-origin Origin/Referer, expired database
  sessions, and site-author versus owner/moderator permission boundaries;
- a concurrent one-request comment rate-limit edge in the existing PostgreSQL
  locking suite.

Browser additions:

- anonymous Feed and post reading;
- search, tag combination/clearing, and pagination;
- Google and GitHub login through deterministic mock provider POST flows;
- comment creation, thread reply, post reaction toggle and participant surface;
- subscription request, explicit confirmation, and explicit unsubscribe;
- credential-bound Draft Mode with a separate public-context isolation check;
- axe analysis, keyboard focus trap, participant/thread Escape behavior, focus
  restoration, and full-screen 375x812 thread layout;
- the same five flows at 375x812, 768x1024, 1440x900, and 1920x1080.

Infrastructure and CI additions:

- marker-selected PostgreSQL tests with `PYTEST_FAIL_ON_SKIP=1`;
- live Compose CSP/HSTS/nosniff/referrer assertions;
- failure-only Playwright artifacts and a scanner for plain files, image bytes,
  and zip entries;
- a final `ci-required` job that rejects activation unless backend SQLite,
  backend PostgreSQL, frontend, Playwright, and full infrastructure jobs all
  succeed.

## Required suites

Milestone 11 treats the following as independent required CI gates:

1. backend format, lint, SQLite tests and production settings check;
2. PostgreSQL migrations, search, locking and concurrency with any skip treated
   as a failure;
3. frontend format, lint, typecheck, Vitest, production build and browser bundle
   scan;
4. Playwright critical flows in deterministic local mock-provider mode;
5. static infrastructure tests and all Compose configuration contracts;
6. full Docker Compose integration, including Nginx, PostgreSQL, backup/restore,
   recovery state, MinIO, worker egress, restart and dynamic DNS.

Release image construction remains downstream of a successful CI workflow, so
failure of any required job prevents activation. No test workflow changes
external OAuth, Resend, S3, DNS, GitHub Environment or production state.

## Artifact policy

- Playwright screenshots and traces are retained only on failure.
- Videos are disabled.
- Test credentials are deterministic non-production sentinels.
- A post-test scanner removes any failure artifact containing secret names,
  known sentinels, internal origins, authorization headers, cookies or session
  identifiers before upload, then verifies the retained set again.
- CI logs and management-command assertions must use identifiers or counts, not
  email addresses, provider tokens, credentials or raw webhook bodies.
