# ADR 0009: Persistent public navigation, cache boundaries, and infinite Feed

- Status: Accepted and exercised on staging
- Date: 2026-08-06

## Context

The Stage 18 public frontend used ordinary anchors for Feed, Bridge, and post
navigation. Every internal click therefore loaded a new document, remounted the
root shell and `AuthProvider`, repeated `/api/me/`, discarded browser Feed and
reaction state, and showed the global Feed-shaped `app/loading.tsx` even on
unrelated routes. Public server fetches carried Next cache tags, but the dynamic
root boundary did not itself establish a reusable Next.js 16 cache scope.

The page-number content API remains a useful bounded transport contract. It is
not a snapshot or cursor contract: a publication between page reads can still
cause an item to move. The low publication rate makes frontend ID
deduplication sufficient for this stage.

## Decision

### Navigation and persistent browser ownership

The root Next.js layout owns the theme, header, footer, `AuthProvider`, and one
long-lived TanStack React Query client. Safe same-origin product routes use
Next.js `Link`; Feed, Bridge, and public post links may fully prefetch. Private
account, login, signup, subscription credential, and other session-sensitive
routes use client navigation with `prefetch={false}`. OAuth initiation, logout,
Draft Mode, revalidation, and other mutation/security endpoints retain normal
form or document semantics.

The React Query client keeps public Feed/search pages, the public reaction
catalog, and viewer reads across route transitions. Viewer query keys include
`anonymous` or `user:<stable-id>`. Login, logout, session expiry, and an
identity change remove the previous viewer namespace and refresh `/api/me/`;
public data is never keyed as viewer data. The existing reaction mutation
coordinator remains the sole owner of in-flight toggle revisions, and comment
reconciliation remains authoritative over comment/thread copies.

### Shared server cache

Next.js `cacheComponents` is enabled. Public list, search, tag metadata, and
detail functions use the supported `"use cache"` directive with:

```text
stale: 30 seconds
revalidate: 60 seconds
expire: 86400 seconds
```

List/search and tag metadata use `posts`. Detail begins with `posts` and
`post-slug:<slug>`, then adds `post:<page-id>` after the authoritative response
reveals the stable ID. The signed revalidation route derives, rather than
accepts, `posts`, `post:<page-id>`, current and previous `post-slug:<slug>`
tags and their public paths for publish, update, unpublish, expiry, and rename.

Draft snapshot resolution is a signed server-to-server POST with
`cache: "no-store"`; Django also returns `private, no-store`. `/api/me/`,
comments, threads, reaction aggregates/toggles, and participants remain
viewer-specific, `private, no-store`, and outside the shared server cache.
Only reaction catalog metadata has a public edge exception with its ETag,
bounded `max-age`, and `stale-while-revalidate` preserved.

### Feed and search

The first Feed/search page is server-rendered for first paint, direct URLs, and
SEO, then seeded into a client `useInfiniteQuery`. Later pages follow only a
validated same-origin relative `next` value. One guarded request may be in
flight; React Query supplies abort signals, query keys isolate each normalized
`q`, and posts are deduplicated by stable ID without reordering the
authoritative pages.

An `IntersectionObserver` sentinel loads older pages. The UI falls back to the
focus-preserving `Load older posts` button when the observer is unavailable,
Save-Data or reduced motion is active, or an append fails. End-of-feed is
reported once as `Beginning of the archive`; appends do not generate repeated
live-region announcements.

Search uses an IME-safe 275 ms debounce and immediate submit. Native
`history.pushState` updates only `q` without starting a server-component
navigation; `popstate` restores the corresponding cached query. Empty search
removes `q`. Legacy `tag` and `page` are normalized away while a valid `q` is
preserved. Tags remain in Wagtail, the API, filtering, indexing, and metadata,
but no public control or visible hashtag exposes them.

Feed page data is owned by the persistent query client, while scroll offsets
are kept per normalized search in `sessionStorage`. Departure is captured
before client navigation and restoration uses an immediate scroll operation so
the global smooth-scroll preference cannot overwrite the saved value.

### Loading and prefetch races

The global Feed-shaped loading boundary is removed. Route-local states describe
only their own data. Safe dynamic public destinations receive full prefetch;
private/session-sensitive destinations do not. The Feed header does not
prefetch its own `/` destination while already on `/`, because that redundant
RSC request can overlap an infinite-page read after invalidation. Bridge and
post pages retain the useful Feed prefetch. Bridge's eight decorative social
images use native lazy loading and asynchronous decoding: React 19 must not emit
their preload links when Feed prefetches Bridge route data, so public route
prefetch remains a data/module optimization rather than a cross-route media
download.

### Subscription and footer surface

The subscription form lives only at `/subscriptions/`. Feed controls expose
one calm client-navigation link, while post pages and the footer contain no
form or subscription link. Confirmation, unsubscribe, CSRF, double opt-in,
cooldown, enumeration resistance, and GET-without-mutation contracts are
unchanged.

The shared public footer is a centered semantic `dl` with exactly two rows,
`Current Team: Yandex` and `Previous Team: Deeplay`, bounded to `34rem` while
retaining the existing type size and responsive gutters.

## Verification and consequences

Browser-contract tests require one document and one `/api/me/` request across
Feed → Bridge → Feed and Feed → post → Back, stable shell node identity,
retained pages, and scroll restoration within two pixels. They also force a
later Feed RSC request to take two seconds and prove a completed public
prefetch is consumed without another request. Cache tests exercise reuse,
publication lifecycle invalidation, slug rename, and Draft isolation; exact
Nginx tests protect private API headers and the one catalog allowlist.

This architecture adds a bounded browser cache and client Feed state, but no
new backend cursor or snapshot claim. Browser history state is intentionally
ephemeral across a full reload beyond the SSR first page, and the application
still relies on the existing page-number API plus ID deduplication during
concurrent publication.
