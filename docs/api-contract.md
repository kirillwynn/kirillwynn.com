# Content API contract

Status: version 1.0

Base path: `/api/v1/`

All timestamps are ISO 8601 UTC strings with a `Z` suffix. Public content and
discussion reads are anonymous and JSON-only. Unknown, draft, unpublished,
future, expired, and restricted posts all produce the normal detail 404.

Frontend-facing absolute local URLs are based on the configured public origin,
not the host of the Django request. `PUBLIC_SITE_URL` defaults locally to
`http://localhost:3000`; production requires a valid HTTP(S) origin with no
path, query, or fragment. A trailing slash is removed. Absolute HTTP(S)
storage URLs, such as S3 or CDN URLs, pass through unchanged.

## Public routes

### `GET /api/v1/posts/`

Query parameters:

- `q`: optional full-text query, trimmed, maximum 200 Unicode code points;
- `tag`: optional exact case-sensitive Unicode tag slug;
- `page`: positive page number;
- `page_size`: default `10`, maximum `50`.

`q` and `tag` combine with AND semantics. Empty `q` after trimming is absent.
Every supported parameter may occur at most once. Queries containing Unicode
control/unassigned/surrogate/private-use code points, queries over the limit,
invalid tag slugs, and malformed page shapes return a field-specific 400
without reflecting the input. Unknown valid tag slugs return a normal empty
page.

The canonical public visibility policy is applied before search and tag
filtering. Draft, unpublished, scheduled-for-future, expired, and restricted
pages cannot match. Without `q`, ordering remains
`(-display_published_at, -pk)`, where the first value is SQL
`COALESCE(original_published_at, first_published_at)`. With `q`, the database
backend orders by relevance and then `-pk`, the deterministic tie-break
implemented by Wagtail 7.4's PostgreSQL and SQLite database compilers.

Post metadata exposes four separate timestamp meanings:

- `published_at`: Wagtail's actual `first_published_at` for this site;
- `updated_at`: Wagtail's actual `last_published_at`;
- `original_published_at`: nullable date when archived material first appeared
  elsewhere;
- `display_published_at`: `original_published_at` when present, otherwise
  `published_at`.

The public UI and Open Graph article publication time use
`display_published_at`. Actual site timestamps remain available and unchanged.
The original date has no effect on visibility, scheduling, expiry, email
audience cutoff, outbox availability, or cache event time.

The list never contains `body`. `next` and `previous` are relative API URLs,
such as `/api/v1/posts/?q=django&tag=python&page=2`; they never include an
origin and preserve every active supported parameter.

The page-number and tag parameters remain a backward-compatible transport and
backend-filtering contract. The Stage 19A public UI does not expose tags,
hashtags, page numbers, Next, or Previous. It server-renders page one and then
follows only a validated same-origin relative `next` through an infinite Feed.
It deduplicates by stable post ID but does not claim snapshot consistency when
publication occurs between page reads. A legacy browser URL removes `tag` and
`page`, preserves a single valid `q`, and does not submit an invisible filter.

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "api_version": "1.0",
      "id": 42,
      "slug": "stable-api-contract",
      "title": "A stable API contract",
      "excerpt": "A short plain-text summary.",
      "published_at": "2026-07-26T17:00:00Z",
      "updated_at": "2026-07-26T17:05:00Z",
      "original_published_at": "2018-04-03T12:00:00Z",
      "display_published_at": "2018-04-03T12:00:00Z",
      "author": {
        "id": 1,
        "display_name": "Kirill Wynn",
        "is_site_author": true
      },
      "tags": [
        { "name": "Django", "slug": "django" },
        { "name": "Wagtail", "slug": "wagtail" }
      ],
      "canonical_path": "/posts/stable-api-contract",
      "canonical_url": "https://kirillwynn.com/posts/stable-api-contract",
      "seo": {
        "title": "A stable API contract",
        "description": "A short plain-text summary."
      },
      "open_graph": {
        "title": "A stable API contract",
        "description": "A short plain-text summary.",
        "image": null
      },
      "lead_image": null
    }
  ]
}
```

### Search index

Production uses Wagtail 7.4's current
`wagtail.search.backends.database` backend over PostgreSQL FTS, with
`django.contrib.postgres` installed. The removed
`wagtail.contrib.postgres_search` backend is not used. PostgreSQL uses the
language-neutral `simple` configuration so Russian, English, and mixed
lexemes share one exact token-matching contract; it deliberately does not
perform language-specific stemming.

`BlogPostPage` uses these explicit boosts:

| Content   | Boost |
| --------- | ----: |
| title     |    10 |
| excerpt   |     7 |
| body text |     4 |
| tag names |     2 |

PostgreSQL maps all project boost values into its four A/B/C/D weight levels.
Body indexing includes rich text with markup stripped, headings, image
contextual alt text, quotes and attribution, list/checklist text, inline/code
content, table cells, and link labels. It excludes heading levels, checklist
booleans, code language identifiers, URLs/destinations, HTML markup, and
divider/service values. Tag names are flattened from the related
`ClusterTaggableManager` into their own boosted search field; the tag slug
remains an indexed related filter field. A `page_published` reindex occurs
after Wagtail has copied cluster child relations so changed tags are present
immediately.

SQLite FTS5 is the local/unit-test fallback. It supports functional field and
Unicode coverage but has different tokenization and scoring; PostgreSQL
weight/ranking assertions are skipped, not simulated, on SQLite. Run
`python manage.py update_index` after deploying a search-field configuration
change so existing rows receive the new document.

### `GET /api/v1/tags/`

This endpoint returns only tags attached to posts accepted by the same public
visibility policy:

```json
{
  "results": [
    {
      "name": "Django",
      "slug": "django",
      "count": 3
    }
  ]
}
```

Results are ordered by `(slug, name)`. `count` is the distinct public post
count. Hidden lifecycle states neither create entries nor increment counts;
the aggregate query is bounded and does not issue one query per tag or post.

### `GET /api/v1/posts/<unicode-slug>/`

The detail resource has the same metadata fields as a list item and adds
`body`. It omits the list-only `lead_image`; the resolved Open Graph image is in
`open_graph.image`. Slugs may contain Unicode letters and numbers, `-`, and
`_`, so both `/api/v1/posts/привет-мир/` and the corresponding percent-encoded
request URL resolve the same resource. A slug never contains `/`.

```json
{
  "api_version": "1.0",
  "id": 42,
  "slug": "stable-api-contract",
  "title": "A stable API contract",
  "excerpt": "A short plain-text summary.",
  "published_at": "2026-07-26T17:00:00Z",
  "updated_at": "2026-07-26T17:05:00Z",
  "original_published_at": "2018-04-03T12:00:00Z",
  "display_published_at": "2018-04-03T12:00:00Z",
  "author": {
    "id": 1,
    "display_name": "Kirill Wynn",
    "is_site_author": true
  },
  "tags": [
    { "name": "Django", "slug": "django" },
    { "name": "Wagtail", "slug": "wagtail" }
  ],
  "canonical_path": "/posts/stable-api-contract",
  "canonical_url": "https://kirillwynn.com/posts/stable-api-contract",
  "seo": {
    "title": "A stable API contract",
    "description": "A short plain-text summary."
  },
  "open_graph": {
    "title": "A stable API contract",
    "description": "A short plain-text summary.",
    "image": null
  },
  "body": [
    {
      "id": "018f7279-2fdb-7ad0-84e3-fd935f078be5",
      "type": "heading",
      "value": { "level": "h2", "text": "Contract" }
    },
    {
      "id": "018f7279-5f7a-740c-b3ec-a76d4f424875",
      "type": "rich_text",
      "value": { "html": "<p>Expanded display HTML.</p>" }
    }
  ]
}
```

Fallbacks:

- `seo.title`: `seo_title`, then page title;
- `seo.description`: `search_description`, then excerpt;
- `open_graph.title`: explicit Open Graph title, then SEO title, then title;
- `open_graph.description`: explicit Open Graph description, then search
  description, then excerpt;
- `open_graph.image`: explicit image, then the first body image, then the first
  gallery image;
- `canonical_url`: explicit canonical URL, otherwise `PUBLIC_SITE_URL` plus the
  URI-encoded `canonical_path`.

Tags are sorted by `(slug, name)`.

The required `author` object is identical in list, detail, and private preview
responses and is derived from Wagtail `Page.owner`. It contains only stable user
ID, current authoritative nickname as `display_name`, and the explicit
`is_site_author` marker. Email, internal username, provider state, staff
permissions, and moderation metadata are never serialized. A nickname change
invalidates Feed and every live post owned by that user through the durable
post revalidation boundary; preview resolution remains private and uncached.

### Public frontend cache consumer

The Next.js 16 frontend enables Cache Components. List/search, available-tag
metadata, and detail fetchers execute inside explicit `"use cache"` scopes with
30-second stale, 60-second revalidation, and 24-hour expiry values. Lists,
searches, and tag metadata use `posts`; details use `posts`,
`post-slug:<slug>`, and the response-derived `post:<page-id>` tag. Cache tags on
an inner `fetch` are retained for compatibility but are not treated as the
cache boundary by themselves.

The first Feed/search page is SSR data and seeds a persistent browser query.
Later pages are viewer-independent public queries. Search query keys use the
normalized Unicode text, and a query change aborts or isolates old requests so
a stale response cannot replace the current result. Browser URL synchronization
uses `history.pushState`/`popstate` and does not start an RSC navigation per
keystroke. Direct search URLs remain server-rendered, canonicalize to `/`, and
are `noindex`.

Authenticated/session data is never stored in this shared cache. `/api/me/` is
a private root-session query that is removed or refreshed at every known
identity boundary. Comments, threads, reaction aggregates, toggles, and
participants remain private browser queries whose keys include `anonymous` or
`user:<stable-id>`; login, logout, session expiry, or an identity change removes
the previous viewer namespace.

## Session authentication

Browser authentication uses Django database-backed sessions and standard Django
CSRF on the same public origin. It does not use JWT, Auth.js/NextAuth,
`localStorage` tokens, or `X-Session-Token`.

### `GET /api/me/`

This endpoint uses DRF `SessionAuthentication` with `AllowAny`. It always calls
Django `get_token()`, sets the CSRF cookie when needed, and returns a masked
CSRF token suitable for a subsequent same-origin POST.

Anonymous response:

```json
{
  "authenticated": false,
  "user": null,
  "providers": {
    "google": { "available": true, "connected": false },
    "github": { "available": true, "connected": false }
  },
  "csrf_token": "<masked token>"
}
```

Authenticated response:

```json
{
  "authenticated": true,
  "user": {
    "id": 123,
    "nickname": "Reader",
    "display_name": "Reader",
    "nickname_suggestion": null,
    "email": "reader@example.com",
    "email_verified": true,
    "profile_complete": true,
    "has_usable_password": true,
    "nickname_change_available_at": null,
    "is_admin": false,
    "is_banned": false,
    "can_interact": true
  },
  "providers": {
    "google": { "available": true, "connected": true },
    "github": { "available": true, "connected": false }
  },
  "csrf_token": "<masked token>"
}
```

`available` means a complete settings-based provider credential pair is present.
`connected` is derived from the user's `SocialAccount` records. `can_interact`
is true only for an authenticated, active, non-banned user with a confirmed
nickname and a verified primary email whose canonical key matches the user.
An inactive user's Django session is rejected and represented as anonymous.
An incomplete OAuth profile also receives a defensive `nickname_suggestion`
derived from the provider name; the backend still validates the submitted
nickname authoritatively.

The response never contains provider `extra_data`, OAuth tokens, a session key,
staff permission details, credentials, or provider payloads. Every response has:

```text
Cache-Control: private, no-store
Vary: Cookie
```

### Local account mutation boundary

The following are the only local account API paths. They accept a bounded JSON
object (`Content-Type: application/json`, default maximum 16 KiB), reject
unknown fields, use `SessionAuthentication`, and require normal same-origin
Django CSRF even before authentication. Every success and error response is
`private, no-store` with `Vary: Cookie`. The canonical browser namespace is
`/api/v1/auth/`. Exact `/api/auth/` aliases remain only for application
rollback compatibility. Unknown paths in either auth namespace are normal
404s; there is no wildcard auth proxy.

Database-backed, HMAC-keyed fixed-window rate limits cover canonical email,
client IP, and authenticated-user scopes across processes and containers;
set/change-password shares both IP and user buckets. A limited request returns
429 with `Retry-After`. Passwords are processed only by Django's configured
password validators and password hasher and are never returned or retained by
the browser after submission.

The exact Nginx locations enforce the same 16 KiB ceiling before proxying and
return a stable JSON 413 with `Cache-Control: private, no-store` and
`Vary: Cookie`; Django independently rechecks the byte length. Rate-limit keys
are HMAC digests rather than raw IP/e-mail values. Each successful bucket
creation opportunistically deletes at most 1,000 same-scope rows older than two
complete windows, bounding cleanup work while preventing indefinite history
growth. Public credential fields remain disabled until `/api/me/` has supplied
the masked CSRF token, so input cannot be lost during hydration.

#### `POST /api/v1/auth/signup/`

Accepts exactly:

```json
{
  "email": "reader@example.com",
  "nickname": "Reader",
  "password": "<new password>",
  "password_confirmation": "<new password>"
}
```

New accounts receive an opaque internal username. Email is the sole public
login identifier. Success and an already registered canonical email both
return 202 with the same generic detail. Nickname availability remains a
public field error, but is evaluated before the existing-email branch so it
cannot be combined with a claimed nickname to enumerate accounts. Signup does
not create a session and the primary `EmailAddress` remains unverified until a
credential is consumed.

#### `POST /api/v1/auth/login/`

Accepts `email`, `password`, and optional `next`. Wrong password, unknown email,
inactive account, and banned account return the same generic 400. A successful
login rotates the database session and returns:

```json
{
  "status": "authenticated",
  "next": "/",
  "requires_profile_completion": false,
  "csrf_token": "<new masked token>"
}
```

For an incomplete migrated local profile,
`requires_profile_completion=true`; the frontend then opens the fixed
`/account/profile` route while retaining only the separately validated product
destination. OAuth callbacks enforce the same profile route on the backend.
The public return-to allowlist itself is not expanded: only `/`, `/bridge`,
`/account`, and one exact `/posts/<slug>` path are valid destinations.

#### Email verification

- `POST /api/v1/auth/verify-email/resend/` accepts exactly `{"email":"..."}`
  and always returns the same 202 response for eligible, unknown, already
  verified, inactive, or banned accounts.
- `POST /api/v1/auth/verify-email/` accepts exactly `{"credential":"..."}`.
  Success is `{"status":"verified"}`. Stable credential states are invalid
  (400), used (409), expired (410), and unavailable (403).

Verification credentials are one-time and bound to purpose, user ID, canonical
email, account-state version, and expiry. The default TTL is 24 hours. The raw
credential is delivered only after `#credential=` and is submitted in this
POST body after the frontend has synchronously removed the fragment with
`history.replaceState`.

#### Password reset, set, and change

- `POST /api/v1/auth/password/reset/` accepts exactly `{"email":"..."}` and
  returns the same 202 response for known and unknown addresses. Only an
  active, non-banned account with a matching verified primary address gets a
  one-hour reset credential.
- `POST /api/v1/auth/password/reset/confirm/` accepts `credential`, `password`,
  and `password_confirmation`. Success invalidates all old sessions and returns
  `{"status":"password_reset"}`. Consumption locks the user before the
  credential/allauth rows and rechecks that the bound canonical address is
  still the unique verified primary identity.
- `POST /api/v1/auth/password/set/` accepts `password` and
  `password_confirmation` for an authenticated OAuth-only account with a
  connected Google or GitHub provider and matching verified primary email. An
  arbitrary `SocialAccount.provider` row is not sufficient. It keeps OAuth
  connections and the current session.
- `POST /api/v1/auth/password/change/` additionally requires
  `current_password`. It changes an existing usable password, invalidates other
  sessions, and preserves the current session through Django's session-auth
  hash update.

Password or relevant account-state changes revoke outstanding credentials.
Credential success clears sensitive component state; no password or credential
uses `localStorage`, `sessionStorage`, a query string, or a response payload.

#### `PATCH /api/v1/auth/profile/`

Accepts exactly `{"nickname":"..."}` for an authenticated, active, non-banned
account. Initial OAuth profile completion has no cooldown. Later user changes
are limited to one every 30 days; a rejection and `/api/me/` expose the exact
next allowed timestamp. Current and historical nickname keys are protected by
database uniqueness, so concurrent signup or rename cannot recycle a claim.

### `POST /api/v1/auth/logout/`

Logout accepts only POST with `Content-Type: application/json` and the exact
empty object `{}`. For an authenticated session,
`SessionAuthentication` requires a valid masked token in `X-CSRFToken` (or the
normal CSRF form field). Success returns `204 No Content`, flushes the Django
session, and has `Cache-Control: private, no-store` plus `Vary: Cookie`.
Repeated anonymous logout is also a safe `204`. Missing or invalid CSRF on an
authenticated session returns `403`; GET returns `405` and never changes state.

### OAuth return destinations

OAuth `next` is a backend-enforced product allowlist rather than an arbitrary
relative URL. Only `/`, `/bridge`, `/account`, and
`/posts/<valid-unicode-slug>` may be retained, with an optional query string.
The raw and strictly decoded value must each begin with exactly one `/`.
Schemes, authorities, fragments, multiple leading slashes, backslashes,
controls, malformed or repeated percent encoding, service routes, and extra
post path segments are discarded. An invalid value is not stored in OAuth state
and the callback redirects to `/`.

## Discussions

Discussion responses depend on the viewer and mutable state. Every discussion
response, including errors, has:

```text
Cache-Control: private, no-store
Vary: Cookie
```

They are fetched directly by the client and never enter the Next.js public
content cache. All mutation routes use DRF `SessionAuthentication`, require an
authenticated active non-banned user, and enforce normal Django CSRF. Anonymous
reads remain available. An anonymous, banned, inactive, or unauthorized
mutation returns `403`.

### Public comment representation

```json
{
  "id": 123,
  "kind": "comment",
  "body": "Plain text only.",
  "status": "visible",
  "author": {
    "id": 42,
    "display_name": "Reader",
    "is_site_author": false
  },
  "thread_root_id": null,
  "reply_to": null,
  "created_at": "2026-07-26T20:00:00.000000Z",
  "updated_at": "2026-07-26T20:00:00.000000Z",
  "edited_at": null,
  "reply_count": 2,
  "last_reply_at": "2026-07-26T20:05:00.000000Z",
  "reactions": [
    {
      "reaction": {
        "id": "pepeclap",
        "name": "Pepe clap",
        "label": "Clapping",
        "kind": "animated",
        "asset_url": "https://media.example/reactions/pepeclap/abc/animation.gif",
        "poster_url": "https://media.example/reactions/pepeclap/abc/poster.webp",
        "width": 128,
        "height": 128,
        "version": "sha256-abc"
      },
      "count": 2,
      "viewer_reacted": false,
      "participants": "/api/v1/comments/123/reactions/pepeclap/participants/"
    }
  ],
  "viewer": {
    "can_edit": false,
    "can_delete": false,
    "can_reply": false,
    "can_react": false
  }
}
```

Replies use `kind: "reply"`, the direct top-level `thread_root_id`, and:

```json
{ "reply_to": { "id": 43, "display_name": "Selected participant" } }
```

The backend derives `reply_to` from the selected comment. Caller-supplied
author, user, thread-root, moderation, or identity fields are rejected.
Provider data, email, SocialAccount data, sessions, CSRF values, and moderation
reasons are never present.

Deleted and hidden comments return `body: null` with `status: "deleted"` or
`status: "hidden"`. Their authors and thread structure remain. The UI renders
neutral `[deleted]` and `[hidden]` tombstones.

### `GET/POST /api/v1/posts/<unicode-slug>/comments/`

`GET` returns only top-level comments for a post accepted by the canonical
public post visibility policy. Ordering is `(-created_at, -id)`.

```json
{
  "next": "/api/v1/posts/post/comments/?cursor=opaque",
  "previous": null,
  "results": []
}
```

Cursor links are relative. Page size is fixed at 20. `reply_count` and
`last_reply_at` are database annotations rather than per-row queries.

`POST` accepts exactly:

```json
{ "body": "A plain-text comment" }
```

Success is `201`. Publication is immediate. Body normalization changes CRLF and
CR to LF, trims outer whitespace, rejects empty input, rejects NUL/C0/C1 and
dangerous bidirectional controls, and limits text to 5000 Unicode code points.
Line breaks and normal Unicode remain valid. HTML-like input is stored and
returned as text, never as renderable markup.

The browser uses the same Unicode code-point limit for root, reply, edit, paste,
counter, and draft paths; HTML `maxlength` is not the authority because browsers
count UTF-16 code units. Anonymous root and reply composers save each change in
a 24-hour, 5000-code-point `sessionStorage` draft scoped by Unicode post slug,
composer kind, thread ID, and `pending-auth`. On OAuth return the draft moves to
the authenticated user namespace and is restored without automatic submission.
Successful submission or explicit discard clears it. Draft storage contains no
CSRF/session/OAuth/provider or user identity data.

### `GET /api/v1/comments/<id>/thread/`

The selected ID may be a root or a reply; both resolve to the direct top-level
root. The root is separate and replies use stable `(created_at, id)`
oldest-first cursor ordering:

```json
{
  "next": null,
  "previous": null,
  "results": [],
  "root": {}
}
```

Replies stay at one level. A deleted or individually hidden comment does not
destroy the thread.

The client reconciles cursor results by numeric comment ID, replaces duplicates
with the freshest server representation, and sorts the raw ISO timestamps plus
numeric ID using the server ordering: roots newest-first and replies
oldest-first. Thread load-more also replaces the root summary returned on that
page, so an optimistic reply cannot double-increment `reply_count`. Cursor URLs
must remain relative and match the exact expected list or thread endpoint.

### `POST /api/v1/comments/<id>/replies/`

The ID is the selected reply target. Selecting a reply reuses its direct root
and derives the mention from that reply's author. A deleted root accepts
replies; a hidden root or hidden selected target does not. Success is `201`.

### `PATCH/DELETE /api/v1/comments/<id>/`

`PATCH` accepts only `{"body": "..."}`. Only the owner may edit a visible,
non-deleted comment. A real body change sets `edited_at`; normalized no-op
edits do not.

`DELETE` is owner-only soft deletion and returns `204`. Repeating it is a safe
`204`. The original body is retained for administrative integrity but is
unconditionally omitted from public serialization. Roots and replies are
locked transactionally, so edit/delete and moderation state changes have
deterministic row-level ordering on PostgreSQL.

### Moderation and rate limits

Django Admin exposes hide/unhide comment actions and ban/unban user actions.
Hide retains body for administrators; unhide restores public display. Hard
delete is disabled for comments and rate buckets in the normal admin UI.

Two database-backed per-user fixed windows are used:

- create/reply: `10` requests per `60` seconds by default;
- edit/delete: `30` requests per `60` seconds by default.

Counts and windows are configured through
`COMMENT_CREATE_RATE_LIMIT_COUNT`,
`COMMENT_CREATE_RATE_LIMIT_WINDOW_SECONDS`,
`COMMENT_MUTATION_RATE_LIMIT_COUNT`, and
`COMMENT_MUTATION_RATE_LIMIT_WINDOW_SECONDS`. Non-positive or malformed values
fail settings initialization. A limit response is `429`, includes
`Retry-After`, and does not create one database row per request. This is normal
application abuse protection, not future edge/DDoS protection.

## Reactions

Reaction reads are anonymous; mutations use the same Django session,
active/non-banned user, and CSRF boundary as comments. Viewer-dependent
aggregates, errors, toggles, and participant pages have:

```text
Cache-Control: private, no-store
Vary: Cookie
```

The user-independent catalog and deprecated rollback-only quick config use the
separate public cache contract documented below. They never vary on session or
cookie state. New public clients consume only the catalog.

Post reaction routes reuse the canonical public post policy. Comment routes
also require a post accepted by that policy. Draft, unpublished, future,
expired, restricted, and unknown targets return 404.

### Canonical catalog identity

Toggle payloads accept exactly:

```json
{ "reaction_id": "pepeclap" }
```

Unexpected or missing fields are rejected. `reaction_id` must be the exact
lowercase ASCII ID of one enabled/selectable manifest-managed catalog item.
Unicode, shortcode, source filename, URL, storage key, Wagtail/database ID,
display label, and arbitrary client objects are never accepted as identity.

Groups are ordered by catalog ordering, then stable catalog ID, and have:

```json
{
  "reaction": {
    "id": "pepeclap",
    "name": "Pepe clap",
    "label": "Clapping",
    "kind": "animated",
    "asset_url": "https://media.example/reactions/pepeclap/abc/animation.gif",
    "poster_url": "https://media.example/reactions/pepeclap/abc/poster.webp",
    "width": 128,
    "height": 128,
    "version": "sha256-abc"
  },
  "count": 12,
  "viewer_reacted": true,
  "participants": "/api/v1/posts/post/reactions/pepeclap/participants/"
}
```

`asset_url` is the static WebP or animated GIF; `poster_url` is always safe to
render as a static fallback. Neither exposes an internal S3 key.
`participants` is the exact relative endpoint for that target and catalog ID.
Disabled catalog items and unmapped legacy Unicode rows are omitted from new
public aggregates without deleting their database rows.

`label` is the complete human-readable accessibility label supplied by the
catalog. A client may add surrounding control grammar such as `React with …`,
but it must not blindly append a second `reaction` suffix when the label
already contains one. Images inside those labelled controls remain decorative
with `alt=""`.

### Post aggregates and toggle

- `GET /api/v1/posts/<unicode-slug>/reactions/`
- `POST /api/v1/posts/<unicode-slug>/reactions/toggle/`

The GET response is:

```json
{ "reactions": [] }
```

Toggle adds the viewer's `(post, catalog item)` row when absent and removes it
when present. A user may hold several different catalog reactions on one post.
It returns the complete authoritative aggregate:

```json
{
  "action": "added",
  "reactions": []
}
```

`action` is `added` or `removed`; clients replace optimistic state with
`reactions`.

### Feed batch post aggregates

`GET /api/v1/reactions/posts/?ids=42,43,44`

This endpoint supplies the viewer-dependent reaction state for one already
loaded Feed page. The public `GET /api/v1/posts/` representation remains
viewer-independent and publicly cacheable; it does not embed
`viewer_reacted`.

The query string accepts exactly one `ids` parameter and no other parameter.
Its value must contain between 1 and 50 unique, positive, canonical ASCII
base-10 integer IDs separated by commas. Signs, whitespace, leading zeroes,
empty items, values above the signed 64-bit integer range, duplicates,
repeated or missing `ids`, and more than 50 IDs receive a stable JSON `400`.

The response is:

```json
{
  "results": [
    {
      "post_id": 42,
      "slug": "привет-мир",
      "reactions": [
        {
          "reaction": {
            "id": "pepeclap",
            "name": "Pepe clap",
            "label": "Clapping",
            "kind": "animated",
            "asset_url": "https://media.example/reactions/pepeclap/abc/animation.gif",
            "poster_url": "https://media.example/reactions/pepeclap/abc/poster.webp",
            "width": 128,
            "height": 128,
            "version": "sha256-abc"
          },
          "count": 1,
          "viewer_reacted": false,
          "participants": "/api/v1/posts/%D0%BF%D1%80%D0%B8%D0%B2%D0%B5%D1%82-%D0%BC%D0%B8%D1%80/reactions/pepeclap/participants/"
        }
      ]
    }
  ]
}
```

Results follow requested-ID order. Unknown IDs and posts rejected by the
canonical public visibility policy are omitted rather than distinguished, so
draft, unpublished, future, expired, and restricted posts are not disclosed.
Visible posts with no aggregate are returned with an empty `reactions` array.
Post selection, aggregate counts, and authenticated viewer state use bounded
page-level queries rather than one query per post.

The endpoint uses Django `SessionAuthentication` while allowing anonymous
reads. Like every reaction response, successes and validation errors include
`Cache-Control: private, no-store` and `Vary: Cookie`. The frontend reaches it
through only the exact same-origin `/api/v1/reactions/posts/` rewrite.

### Comment aggregates and toggle

- `GET /api/v1/comments/<id>/reactions/`
- `POST /api/v1/comments/<id>/reactions/toggle/`

The shapes match post reactions. Top-level comments and replies use the same
contract. Comment list and thread representations embed their aggregate and
viewer state, loaded in bounded grouped queries for the whole cursor page.

Deleted or hidden tombstones return an empty aggregate, never expose
participants, and reject new toggles with 403. Existing rows remain for
moderation history. Client reconciliation preserves reactions only while a
specific optimistic mutation revision is pending. The matching authoritative
or rollback result clears that marker, after which later comment, thread, edit,
or cursor responses may replace the aggregate. An older mutation result cannot
settle a newer revision, and a tombstone always clears both reactions and the
pending marker.

Reaction mutation ownership is shared by every mounted representation of one
concrete `(target kind, target ID)`. The coordinator permits one in-flight
toggle per target, assigns revisions globally across coordinator-owned
mutations, and broadcasts the same optimistic, busy, authoritative, or rollback
snapshot to list and thread copies. The network request and settlement outlive
the initiating component subscription: closing a thread removes that
subscriber but the remaining comment card still receives the matching result
and clears its transient marker. A different target has an independent
single-flight slot. Component-local lifecycle checks do not own or discard the
mutation result.

### Participants

- `GET /api/v1/posts/<unicode-slug>/reactions/<reaction-id>/participants/`
- `GET /api/v1/comments/<id>/reactions/<reaction-id>/participants/`

Participants use a fixed page size of 20 and stable `(created_at, id)` cursor
ordering. `next` and `previous` are relative and must match the same exact
target/catalog-ID endpoint.

```json
{
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 42,
      "display_name": "Kirill",
      "is_site_author": false
    }
  ]
}
```

Email, OAuth/provider identity, tokens, session information, and moderation
metadata are never present.

The client gives each participant request an identity and abort signal.
Switching target or reaction ID, closing the surface, or unmounting invalidates
the previous request; stale successes and failures cannot update the current
group.
Cursor pages are accepted only for the current group and are deduplicated by
participant ID. Escape closes the participant surface and returns focus to its
trigger. On every post, Feed, comment, reply, and thread surface, hover,
`pointerenter`, focus alone, and a synthetic mouse event after touch neither
open participants nor issue a participant request. Participants open only
after click/tap or native Enter/Space activation of the exact count button.
Outside pointer dismissal consumes the closing event so it cannot activate an
underlying reaction control; an intentional click on another focusable element
is not overridden by forced restoration to the old trigger.
Any reaction mutation event for the displayed target closes the current
participant surface before applying the optimistic or authoritative snapshot,
so a removed or replaced aggregate cannot leave a stale participant dialog.

### Public catalog and rollback-only quick config

`GET /api/v1/reactions/catalog/`

```json
{
  "version": "sha256-catalog-payload-digest",
  "results": [
    {
      "id": "pepeclap",
      "name": "Pepe clap",
      "label": "Clapping",
      "kind": "animated",
      "asset_url": "https://media.example/reactions/pepeclap/abc/animation.gif",
      "poster_url": "https://media.example/reactions/pepeclap/abc/poster.webp",
      "width": 128,
      "height": 128,
      "version": "sha256-abc"
    }
  ]
}
```

Only enabled/selectable allowlisted items appear, in deterministic catalog
order. The endpoint contains descriptors, not source paths, provenance,
storage keys, hashes other than public immutable versions, or viewer state.

`GET /api/v1/reactions/config/`

This endpoint is deprecated and retained only so the previous staging frontend
digest remains a safe rollback target. The current public UI does not request
it, does not expose suggested/quick reactions, and does not use it to restore
OAuth pending intents.

```json
{
  "quick_reactions": [
    {
      "id": "pepeclap",
      "name": "Pepe clap",
      "label": "Clapping",
      "kind": "animated",
      "asset_url": "https://media.example/reactions/pepeclap/abc/animation.gif",
      "poster_url": "https://media.example/reactions/pepeclap/abc/poster.webp",
      "width": 128,
      "height": 128,
      "version": "sha256-abc"
    }
  ]
}
```

The rollback response continues to contain the three distinct
enabled/selectable descriptors stored in `ReactionSettings`. The model, its
three catalog foreign keys, the existing `pepeclap` / `pepehmm` / `pepelove`
values, and catalog `quick_order` remain unchanged during the compatibility
window. The active Wagtail quick-selection form is no longer registered in the
owner navigation. No Wagtail model IDs or internal metadata are returned.

Both endpoints are fully user-independent and return:

```text
Cache-Control: public, max-age=60, stale-while-revalidate=300
ETag: "<sha256>"
```

They do not vary on `Cookie`; an exact `If-None-Match` receives `304`.
The staging/integration edge has an exact allowlisted catalog location that
preserves this upstream ETag and cache policy. The general `/api/v1/` private
policy still applies to reaction aggregates, participants, comments, and
session data; no wildcard public reaction exception exists.

Post detail, top-level comment, reply, and thread instances render only
existing aggregate pills with counts plus exactly one compact `Choose
reaction` picker trigger. A surface with no aggregate renders only that
trigger. No suggested reaction descriptor or image is rendered before the
picker opens. Feed remains aggregate-only and has no picker trigger.

The picker shell is part of the reaction bar and appears before its lazy module
or catalog resolves. The lazy module and catalog query are started in parallel
after browser idle or pointer-enter/focus/pointer-down intent; Save-Data skips
idle/hover prefetch but an explicit opening may load them. Neither prefetch
loads reaction images. One persistent module promise and one shared React Query
catalog key serve duplicate bars and survive public route navigation. A valid
pending catalog ID not present in aggregate groups restores through this same
catalog endpoint, never the deprecated config endpoint.
Search uses display and accessibility labels. Posters and static assets are
intersection-gated: an offscreen picker item has no image element or `src`,
rather than relying only on browser `loading=lazy`. The animation URL is
selected only for an intersecting active item. With
`prefers-reduced-motion: reduce`, the animation URL is never assigned. Leaving
the viewport restores the poster. An image failure falls back from animation
to poster and then to accessible text.

Recent and pending reaction storage is schema version 2 and stores catalog IDs
only. IDs use the same bounded lowercase ASCII shape as the API. Asset URLs and
internal storage keys are never persisted. Version-1 Unicode recent/pending
entries are removed or ignored without an implicit mapping.

At most one pending reaction intent exists for one
`(slug, target kind, target ID)`. Saving another catalog ID removes older
intents for that target. Valid version-2 duplicates are selected by greatest
`createdAt` and compacted to one entry; confirm and discard clear the whole
target namespace. Other targets remain isolated and the ten-minute TTL is
unchanged. OAuth never auto-submits a restored intent.

Physical removal of the config endpoint, `ReactionSettings` quick catalog
fields, and catalog `quick_order` is a separate cleanup migration after the
rollback compatibility window. This remediation does not run catalog sync or
alter catalog rows, identity, manifests, hashes, asset versions, or objects.

### Concurrency and rate limit

Toggles lock the concrete post or comment row in one database transaction.
This serializes all competing toggles for a target; the unique
`(target, user, catalog item)` constraint is the final duplicate boundary. Two
sequential same-user/same-catalog-ID toggles return to the original state.

Legacy rows retain their Unicode column and the old conditional uniqueness.
They are not returned by the custom catalog API, and no automatic mapping is
performed. The legacy column is not removed in this release.

One database-backed fixed-window bucket is locked per user. Defaults are 60
toggle requests per 60 seconds, configured through
`REACTION_TOGGLE_RATE_LIMIT_COUNT` and
`REACTION_TOGGLE_RATE_LIMIT_WINDOW_SECONDS`. Invalid/non-positive settings fail
initialization. A limit response is 429 with integer `Retry-After`.

## Email subscriptions

Subscription responses are `private, no-store`, JSON-only, and never return an
email, subscriber UUID, provider data, or internal lifecycle state.

Stage 19A does not change an API response shape. It moves the anonymous form to
the public `/subscriptions/` page; Feed and post pages no longer embed it.
Viewing that page performs no subscription mutation. Confirmation and
unsubscribe paths and their explicit POST-only mutation boundary are unchanged.
Production email configuration uses provider-independent
`EMAIL_FROM_ADDRESS`; it is snapshotted before outbox creation and validated
before a transaction can reach a database constraint. Maximum authored titles
produce the full immutable `New post: <title>` subject without truncation.
Provider request fingerprints are internal and come from the exact bytes
selected by the configured adapter.

### `POST /api/v1/subscriptions/`

This anonymous browser endpoint still requires the normal same-origin CSRF
token. It accepts exactly:

```json
{ "email": "reader@example.com" }
```

Email input is trimmed, limited to 320 Unicode code points, validated, and
canonicalized by case-folding the complete local part plus IDNA/lowercase
domain conversion. Valid new, pending, active, unsubscribed, and suppressed
identities all receive the same 202:

```json
{
  "detail": "If the address can be subscribed, a confirmation email will be sent."
}
```

Pending resend requests have a cooldown. Active identities do not receive
confirmation loops, unsubscribed identities begin a new double opt-in, and
suppressed identities cannot self-reactivate.

### `POST /api/v1/subscriptions/confirm/`

Accepts exactly:

```json
{ "credential": "<opaque confirmation credential>" }
```

The credential is purpose-bound, subscriber-bound, versioned, and expires
after 48 hours by default. Its signed timestamp is the delivery's one immutable
credential issue time, so a provider retry cannot restart the TTL. Success is
`{"status":"confirmed"}`; repeating the same valid confirmation returns
`{"status":"already_confirmed"}`. Invalid, expired, tampered, wrong-purpose,
superseded, and unknown credentials share a 400 response and message. GET
returns 405 and never confirms.

### `POST /api/v1/subscriptions/unsubscribe/`

Accepts the same one-field shape with a purpose-bound unsubscribe credential.
Success is `{"status":"unsubscribed"}` and a repeated current credential
returns `{"status":"already_unsubscribed"}`. GET returns 405.

The mutation immediately skips deliveries that have not been claimed. A
delivery whose provider call has started is not presented as cancelled: the
worker records provider acceptance if it occurs, while the subscriber remains
unsubscribed and cannot be claimed for later sends.

Human confirmation and unsubscribe pages are
`/subscriptions/confirm/` and `/subscriptions/unsubscribe/`. The credential is
transported in `#credential=...`, removed from the address before interaction,
and kept only in component memory. Both pages are `noindex` with
`no-referrer`; only an explicit button POST mutates state. Draft Mode does not
render a subscription form.

### One-click unsubscribe

`POST /api/v1/subscriptions/unsubscribe/one-click/?credential=<opaque>` is the
CSRF-exempt RFC 8058 boundary for email clients. It accepts only:

```text
Content-Type: application/x-www-form-urlencoded

List-Unsubscribe=One-Click
```

It returns a non-enumerating 200. GET and other bodies do not mutate state.

### Anonymous rate limits

Subscribe consumes separate fixed-window canonical-email and client-IP
buckets. Confirm consumes an IP bucket. Keys are HMAC digests scoped by
operation; raw IPs and rate-limit email values are not retained.
`ALLAUTH_TRUSTED_PROXY_COUNT` selects the client from the right side of
`X-Forwarded-For`. A 429 includes integer `Retry-After`.

### `POST /api/v1/email/webhooks/resend/`

This sessionless/CSRF-exempt provider route accepts only POST and a bounded raw
body. It verifies the exact raw bytes with the configured Svix secret and
`svix-id`, `svix-timestamp`, and `svix-signature` before JSON/business logic,
then applies the configured timestamp replay window. `svix-id` is durably
unique.

Handled types are `email.delivered`, `email.bounced`, and
`email.complained`. Lookup uses only the stored Resend message ID. Permanent
bounce and complaint suppress the related subscriber. A recognized event that
arrives before the worker commits its Resend message ID is stored as a bounded
`pending` correlation record and returns 200. The worker reconciles it after
provider acceptance; `reconcile_email_webhooks` is the bounded crash/restart
backstop. Exact `svix-id` replays remain idempotent, terminal bounce/complaint
wins over late delivered, and multiple pending events apply in
`(occurred_at, received_at, id)` order.

Unknown event types are immediately ignored. A recognized but foreign message
ID remains pending for seven days, then becomes ignored; applied/ignored
idempotency rows are retained for 30 days and the reconciliation command
deletes expired history in bounded batches. This avoids webhook retry storms
while bounding unmatched growth. Stored fields are only event type, bounded
provider message ID, provider occurrence time, normalized bounce
classification, processing state, and correlation timestamps. Raw provider
payloads are never stored.

## StreamField discriminated union

Every block has exactly `id`, `type`, and `value`. `id` is Wagtail's stable
StreamField block UUID.

| `type`               | Exact `value` shape                                                |
| -------------------- | ------------------------------------------------------------------ |
| `rich_text`          | `{"html": "<p>Wagtail-expanded display HTML</p>"}`                 |
| `heading`            | `{"level": "h2" \| "h3" \| "h4", "text": "..."}`                   |
| `image`              | image representation below                                         |
| `gallery`            | `{"images": [<image>, ...]}`                                       |
| `quote`              | `{"text": "...", "attribution": "..." \| null}`                    |
| `bulleted_list`      | `{"items": ["...", "..."]}`                                        |
| `numbered_list`      | `{"items": ["...", "..."]}`                                        |
| `checklist`          | `{"items": [{"text": "...", "checked": true}]}`                    |
| `inline_code`        | `{"code": "..."}`                                                  |
| `code_block`         | `{"language": "python", "code": "..."}`                            |
| `table`              | `{"rows": [["A", "B"]], "header": {"row": true, "column": false}}` |
| `horizontal_divider` | `{}`                                                               |
| `link`               | link representation below                                          |

Rich text uses Wagtail `expand_db_html`. The authoring block enables only bold,
italic, and link features; there is no raw HTML block.

Internal links use frontend routes:

```json
{
  "text": "Read next",
  "kind": "internal",
  "href": "/posts/next-post",
  "target": { "id": 43, "type": "blog.blogpostpage", "slug": "next-post" }
}
```

`BlogIndexPage` maps to `/`; `BlogPostPage` maps to `/posts/<slug>`. External
links have `kind: "external"`, an HTTP(S) `href`, and `target: null`.

## Image representation

The server owns the filter specs. Public callers cannot request arbitrary
renditions.

```json
{
  "id": 7,
  "title": "Snow in the mountains",
  "alt": "A trail crossing a snowy ridge",
  "decorative": false,
  "width": 2400,
  "height": 1600,
  "renditions": {
    "480w": {
      "url": "https://kirillwynn.com/media/images/ridge.width-480.jpg",
      "width": 480,
      "height": 320
    },
    "960w": {
      "url": "https://kirillwynn.com/media/images/ridge.width-960.jpg",
      "width": 960,
      "height": 640
    },
    "1440w": {
      "url": "https://kirillwynn.com/media/images/ridge.width-1440.jpg",
      "width": 1440,
      "height": 960
    }
  }
}
```

Small originals are not upscaled, so returned dimensions can be below the
rendition key. Relative local media URLs use `PUBLIC_SITE_URL`. Absolute
HTTP(S) S3/CDN URLs are returned unchanged.

## Preview resolution

`POST /api/v1/preview/resolve/`

```json
{ "credential": "<opaque short-lived credential>" }
```

On success, the response body is exactly the detail contract. It always sends:

```text
Cache-Control: private, no-store
Pragma: no-cache
```

Invalid, expired, tampered, wrong-page, and wrong-content-type credentials all
return:

```json
{ "detail": "Preview is unavailable." }
```

with status 404. Public post endpoints do not accept preview credentials.
Draft snapshots preserve both archive fields. A never-published draft with no
archive date returns null for `published_at` and `display_published_at`; an
archive draft can return a non-null `original_published_at` and
`display_published_at` while `published_at` remains null.

## Cache revalidation payload

Django sends `POST /api/revalidate` to Next.js with canonical compact JSON:

```json
{
  "action": "updated",
  "event_id": "d9428888-122b-4b16-9f86-4d959146b441",
  "occurred_at": "2026-07-26T17:05:00Z",
  "page_id": 42,
  "previous_slug": "old-slug",
  "slug": "stable-api-contract"
}
```

`previous_slug` is optional. Allowed actions are `published`, `updated`,
`unpublished`, and `expired`. The caller cannot supply cache tags or paths.

Headers:

```text
X-Revalidation-Timestamp: <Unix seconds>
X-Revalidation-Signature: v1=<HMAC-SHA256 hex>
```

The signed bytes are:

```text
<timestamp>.<exact raw request body>
```

Next.js accepts the default 300-second window and derives only:

- tags `posts`, `post:<page_id>`, and `post-slug:<slug>`;
- `post-slug:<previous_slug>` when a rename supplies a distinct previous slug;
- paths `/`, `/posts/<slug>`, and the optional previous-slug post path.

All list/search/filter variants and the available-tag fetch use `posts`.
Stage 19A detail scopes also use `posts`, `post-slug:<slug>`, and the
response-derived stable `post:<page_id>` tag. Publication, update (including
body, tags, author display, or original publication date), privacy transitions,
unpublication, expiry, and slug rename therefore invalidate the shared Feed and
the affected current/previous detail identities without accepting tags or
paths from a browser.

Current and previous slugs may use Unicode letters and numbers, `-`, and `_`,
up to 255 Unicode code points. Slash, backslash, control characters, empty
values, and dot segments are rejected before invalidation.
