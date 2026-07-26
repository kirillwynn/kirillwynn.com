# ADR 0002: Versioned content API, immutable preview snapshots, and revalidation

Status: accepted

Date: 2026-07-26

## Context

The Wagtail content model now needs a stable public contract for Next.js without
exposing drafts or coupling the frontend to Wagtail's internal representation.
Headless preview must render exactly the editor snapshot that was requested.
Publication cache invalidation must survive frontend downtime without making a
successful Wagtail publication fail.

`wagtail-headless-preview` 0.9.0 supports Django 5.2 and Wagtail 7, and its
redirect mode is appropriate for Wagtail 7.4. Its built-in `PagePreview` stores
serialized page content, but its signed token is deterministic per page and its
validation does not apply a `max_age`. Its `created_at` is date-only. The package
token therefore is not the application's preview authorization boundary.

## Decision

### Content API

Use an explicit application-owned DRF contract under `/api/v1/`:

- `GET /api/v1/posts/`;
- `GET /api/v1/posts/<slug>/`;
- `POST /api/v1/preview/resolve/`.

The contract includes `api_version: "1.0"` on content resources. Public
querysets use one reusable visibility policy: the page must be live, public,
published, due, and not expired at request time. The API is anonymous and
read-only. It does not expose Wagtail API v2 fields or query controls.

The explicit DRF contract was selected over exposing Wagtail API v2 directly so
that field names, frontend routes, fallbacks, image sizes, and the StreamField
union remain stable while Wagtail models evolve. GraphQL is not introduced.

### StreamField

Every body item is a discriminated union:

```json
{"id": "<stable StreamField block UUID>", "type": "<block type>", "value": {}}
```

All 13 first-version block types have typed values. Rich text is expanded with
Wagtail's official rich-text expansion, tables are row arrays plus header
metadata, and links contain frontend routes rather than Wagtail serving routes.
Images expose contextual alt/decorative data and a fixed rendition set at
widths 480, 960, and 1440. Public callers cannot provide image filter specs.

### Preview

`wagtail-headless-preview==0.9.0` supplies Wagtail editor integration and the
initial serialized preview. The application copies that content into its own
immutable `PreviewSnapshot` row and issues a credential consisting of a
cryptographically random opaque value protected by Django `TimestampSigner`.
Only a keyed digest of the complete credential is stored.

The default TTL is 600 seconds and is environment-configurable. Resolution
applies `max_age`, checks the expected content type and stable page ID, and
reconstructs only the stored snapshot. There is no "latest draft" lookup and no
page or revision selector.

Wagtail transfers the credential to the same-origin Next.js draft entry in a
short-lived HttpOnly, SameSite=Lax cookie, avoiding a credential in the redirect
URL. Next.js verifies it server-to-server, enables Draft Mode, rotates it into a
separate short-lived HttpOnly preview cookie, removes the entry cookie, and
redirects only to the verified `/posts/<slug>` route. Preview resolution is
`private, no-store`; public content endpoints do not accept preview credentials.
The existing Django-template preview remains available as a separate backend
preview mode.

### Cache revalidation

Wagtail publish and unpublish signals create a `RevalidationEvent` in the same
database transaction as the lifecycle change. The payload contains only:

- event ID;
- action;
- stable page ID;
- current slug;
- optional previous slug;
- UTC occurrence timestamp.

Delivery is a POST to the configured Next.js route. The signature is
HMAC-SHA256 over `<unix timestamp>.<raw JSON body>`, sent as
`X-Revalidation-Timestamp` and `X-Revalidation-Signature: v1=<hex>`. Next.js
uses constant-time comparison and a 300-second default acceptance window. It
derives the allowlisted `posts` and `post:<page-id>` tags and `/` plus
`/posts/<slug>` paths; callers cannot supply tags or paths. Next.js 16.2 uses
`revalidateTag(tag, "max")`.

### Failure and retry

Events move through pending, processing, and delivered states and have a UUID,
attempt count, timestamps, and a bounded sanitized last error. A management
command claims pending or stale-processing rows transactionally, performs HTTP
only after the claim transaction commits, and returns failures to pending.
Non-2xx and network failures are retained. Re-delivery is safe because
revalidation operations are idempotent and Next.js recognizes duplicate event
IDs within a bounded in-process window.

No Redis or Celery is added. Production scheduling of the retry command remains
an infrastructure milestone.

### Next.js boundary

Milestone 3 adds only `frontend/next/` with App Router, strict TypeScript, Draft
Mode entry/exit, a diagnostic server-rendered post route, and the signed
revalidation handler. It deliberately excludes the public feed, final block
renderer, Tailwind, Bridge, and visual design.

## Consequences

Positive:

- the public API cannot accidentally inherit Wagtail internal or preview fields;
- preview credentials authorize one immutable snapshot for a bounded time;
- failed cache delivery cannot undo or lose publication;
- frontend invalidation inputs are fully derived and allowlisted.

Negative:

- the project maintains serializers and matching TypeScript types;
- preview snapshots and delivered outbox rows require retention/cleanup policy;
- immediate delivery still depends on runtime configuration, and periodic retry
  scheduling is deferred;
- the in-process duplicate registry is not shared across Next.js instances, but
  repeated invalidation remains safe.

## Revisit conditions

Revisit this decision if content localization requires contract negotiation,
preview must cross unrelated origins, or the deployment moves to multiple
frontend instances that require a durable shared idempotency registry.
