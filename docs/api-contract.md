# Content API contract

Status: version 1.0

Base path: `/api/v1/`

All timestamps are ISO 8601 UTC strings with a `Z` suffix. Public endpoints are
anonymous, JSON-only, and read-only. Unknown, draft, unpublished, future,
expired, and restricted posts all produce the normal detail 404.

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
