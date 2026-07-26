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

- `page`: positive page number;
- `page_size`: default `10`, maximum `50`.

The list never contains `body`. `next` and `previous` are relative API URLs,
such as `/api/v1/posts/?page=2`; they never include an origin.

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
      "tags": [
        {"name": "Django", "slug": "django"},
        {"name": "Wagtail", "slug": "wagtail"}
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
  "tags": [
    {"name": "Django", "slug": "django"},
    {"name": "Wagtail", "slug": "wagtail"}
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
      "value": {"level": "h2", "text": "Contract"}
    },
    {
      "id": "018f7279-5f7a-740c-b3ec-a76d4f424875",
      "type": "rich_text",
      "value": {"html": "<p>Expanded display HTML.</p>"}
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
    "google": {"available": true, "connected": false},
    "github": {"available": true, "connected": false}
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
    "display_name": "Reader",
    "email": "reader@example.com",
    "is_admin": false,
    "is_banned": false,
    "can_interact": true
  },
  "providers": {
    "google": {"available": true, "connected": true},
    "github": {"available": true, "connected": false}
  },
  "csrf_token": "<masked token>"
}
```

`available` means a complete settings-based provider credential pair is present.
`connected` is derived from the user's `SocialAccount` records. `can_interact`
is false for banned users; an inactive user's Django session is rejected and is
therefore represented as anonymous.

The response never contains provider `extra_data`, OAuth tokens, a session key,
staff permission details, credentials, or provider payloads. Every response has:

```text
Cache-Control: private, no-store
Vary: Cookie
```

### `POST /api/auth/logout/`

Logout accepts only POST. For an authenticated session,
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
      "emoji": "🔥",
      "count": 2,
      "viewer_reacted": false,
      "participants": "/api/v1/comments/123/reactions/%F0%9F%94%A5/participants/"
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
{"reply_to": {"id": 43, "display_name": "Selected participant"}}
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
{"body": "A plain-text comment"}
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
active/non-banned user, and CSRF boundary as comments. Every reaction response,
including config, errors, aggregates, toggles, and participant pages, has:

```text
Cache-Control: private, no-store
Vary: Cookie
```

Post reaction routes reuse the canonical public post policy. Comment routes
also require a post accepted by that policy. Draft, unpublished, future,
expired, restricted, and unknown targets return 404.

### Canonical emoji key

Toggle payloads accept exactly:

```json
{"emoji": "👩‍💻"}
```

Unexpected fields are rejected. Django requires a string, normalizes it to NFC,
limits it to 32 Unicode code points and 128 UTF-8 bytes, and accepts exactly one
standard RGI Unicode emoji sequence through `emoji` 2.15.0. ZWJ sequences,
skin-tone modifiers, flags, keycaps, gender variants, and meaningful variation
selectors are preserved. Text, multiple emoji, shortcode/custom emoji,
whitespace, controls/bidi formatting, lone components, and malformed sequences
are rejected. Surrogate code points are rejected before UTF-8 encoding, with a
defensive encoding-error conversion at the same boundary. Raw JSON such as
`{"emoji":"\ud800"}` therefore receives the normal JSON 400 validation
response rather than an HTML or Unicode encoding 500. Model saves and Wagtail
quick-reaction saves use the same boundary.

Groups are ordered by canonical emoji key and have:

```json
{
  "emoji": "🔥",
  "count": 12,
  "viewer_reacted": true,
  "participants": "/api/v1/posts/post/reactions/%F0%9F%94%A5/participants/"
}
```

`participants` is an exact relative endpoint for that target and emoji.

### Post aggregates and toggle

- `GET /api/v1/posts/<unicode-slug>/reactions/`
- `POST /api/v1/posts/<unicode-slug>/reactions/toggle/`

The GET response is:

```json
{"reactions": []}
```

Toggle adds the viewer's `(post, emoji)` row when absent and removes it when
present. A user may hold several different emoji on one post. It returns the
complete authoritative aggregate:

```json
{
  "action": "added",
  "reactions": []
}
```

`action` is `added` or `removed`; clients replace optimistic state with
`reactions`.

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

### Participants

- `GET /api/v1/posts/<unicode-slug>/reactions/<emoji>/participants/`
- `GET /api/v1/comments/<id>/reactions/<emoji>/participants/`

Participants use a fixed page size of 20 and stable `(created_at, id)` cursor
ordering. `next` and `previous` are relative and must match the same exact
target/emoji endpoint.

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
Switching target or emoji, closing the surface, or unmounting invalidates the
previous request; stale successes and failures cannot update the current group.
Cursor pages are accepted only for the current group and are deduplicated by
participant ID. Escape closes the participant surface and returns focus to its
trigger. Hover opens participants only for a fine, hover-capable mouse pointer;
focus and the explicit count button remain the keyboard/touch paths.

### Quick reaction config

`GET /api/v1/reactions/config/`

```json
{"quick_reactions": ["👍", "❤️", "🎉"]}
```

The three distinct canonical values come from the Wagtail
`ReactionSettings` Site Setting. No Wagtail model IDs or internal metadata are
returned.

The browser uses the compact deterministic `emoji-regex` 10.6.0 sequence data
for storage hygiene, plus NFC/control/limit checks and rejection of redundant
variation selector 16 after a default emoji-presentation code point. The full
Emoji Mart dataset remains behind the lazy picker import. Recent and pending
storage therefore reject incomplete ZWJ/flag sequences and overqualified
values such as `🔥️` and `☕️` without adding the picker dataset to the initial
post bundle. Django remains authoritative.

At most one pending reaction intent exists for one
`(slug, target kind, target ID)`. Saving another emoji removes older intents
for that target. Legacy duplicates are selected by greatest `createdAt` and
compacted to one entry; confirm and discard clear the whole target namespace.
Other targets remain isolated and the ten-minute TTL is unchanged.

### Concurrency and rate limit

Toggles lock the concrete post or comment row in one database transaction.
This serializes all competing toggles for a target; the unique
`(target, user, emoji)` constraint is the final duplicate boundary. Two
sequential same-user/same-emoji toggles return to the original state.

One database-backed fixed-window bucket is locked per user. Defaults are 60
toggle requests per 60 seconds, configured through
`REACTION_TOGGLE_RATE_LIMIT_COUNT` and
`REACTION_TOGGLE_RATE_LIMIT_WINDOW_SECONDS`. Invalid/non-positive settings fail
initialization. A limit response is 429 with integer `Retry-After`.

## StreamField discriminated union

Every block has exactly `id`, `type`, and `value`. `id` is Wagtail's stable
StreamField block UUID.

| `type` | Exact `value` shape |
| --- | --- |
| `rich_text` | `{"html": "<p>Wagtail-expanded display HTML</p>"}` |
| `heading` | `{"level": "h2" \| "h3" \| "h4", "text": "..."}` |
| `image` | image representation below |
| `gallery` | `{"images": [<image>, ...]}` |
| `quote` | `{"text": "...", "attribution": "..." \| null}` |
| `bulleted_list` | `{"items": ["...", "..."]}` |
| `numbered_list` | `{"items": ["...", "..."]}` |
| `checklist` | `{"items": [{"text": "...", "checked": true}]}` |
| `inline_code` | `{"code": "..."}` |
| `code_block` | `{"language": "python", "code": "..."}` |
| `table` | `{"rows": [["A", "B"]], "header": {"row": true, "column": false}}` |
| `horizontal_divider` | `{}` |
| `link` | link representation below |

Rich text uses Wagtail `expand_db_html`. The authoring block enables only bold,
italic, and link features; there is no raw HTML block.

Internal links use frontend routes:

```json
{
  "text": "Read next",
  "kind": "internal",
  "href": "/posts/next-post",
  "target": {"id": 43, "type": "blog.blogpostpage", "slug": "next-post"}
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
{"credential": "<opaque short-lived credential>"}
```

On success, the response body is exactly the detail contract. It always sends:

```text
Cache-Control: private, no-store
Pragma: no-cache
```

Invalid, expired, tampered, wrong-page, and wrong-content-type credentials all
return:

```json
{"detail": "Preview is unavailable."}
```

with status 404. Public post endpoints do not accept preview credentials.

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

List fetches use `posts`; detail fetches use their `post-slug:<slug>` tag
without the global list tag. Stable-ID tags remain available to caches keyed by
page identity. This keeps one post update from evicting every cached detail.

Current and previous slugs may use Unicode letters and numbers, `-`, and `_`,
up to 255 Unicode code points. Slash, backslash, control characters, empty
values, and dot segments are rejected before invalidation.
