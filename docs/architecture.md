# Target architecture

Status: accepted

Last updated: 2026-07-27

## System context

`kirillwynn.com` is a personal publishing product with:

- a public feed and full post pages;
- a bridge page containing external profile links;
- desktop content authoring;
- Google and GitHub authentication;
- Slack-style comment threads;
- Unicode emoji reactions;
- search, tags, media, and email subscriptions;
- isolated staging and production environments.

The old Flask implementation is reference material, not a compatibility target.

## Service boundaries

```text
Browser
   |
 Nginx
   |-- /*          -> Next.js
   |-- /api/*      -> Django REST API
   |-- /cms/*      -> Wagtail Admin
   |-- /accounts/* -> django-allauth
   `-- /media/*    -> Django/Wagtail/S3

Next.js ---- internal HTTP ----> Django/Wagtail
                                  |
                                  |-- PostgreSQL
                                  |-- S3-compatible storage
                                  `-- email provider

Worker -------------------------> scheduled publishing and email outbox
```

All browser-facing services share one origin. Nginx owns external routing and
TLS termination.

## Backend

### Django

Django owns:

- users and sessions;
- OAuth identities;
- comments and threads;
- reactions;
- subscriptions and delivery state;
- authorization and moderation;
- application APIs;
- durable background work state.

The custom user model must exist before the first baseline migration.

### Wagtail

Wagtail owns:

- post content;
- drafts and live state;
- revisions and rollback;
- preview;
- scheduled publishing and unpublishing;
- images and documents;
- tags and editorial metadata;
- future author/editor permissions.

The authoring interface targets desktop browsers. Mobile authoring is not a
first-version requirement.

### REST API

Use Django REST Framework and Wagtail's REST capabilities.

The public API exposes only live content. Draft content is available only
through a short-lived signed preview flow.

GraphQL is deliberately excluded.

## Content model

### Pages

- `BlogIndexPage` represents the feed root.
- `BlogPostPage` represents an article.

`BlogPostPage` includes:

- stable slug;
- title and excerpt;
- publication metadata;
- SEO and Open Graph fields;
- tags;
- Wagtail `StreamField` body;
- Wagtail live/draft/revision state.

### StreamField blocks

The first-version block library includes:

- rich text;
- heading;
- image;
- gallery;
- quote;
- bulleted and numbered lists;
- checklist;
- inline code;
- code block with language metadata;
- table;
- horizontal divider;
- link.

Embeds are deferred until their rendering and security policy is defined.

### Search

Use Wagtail's PostgreSQL database search backend.

Index:

- title with boost 10;
- excerpt with boost 7;
- textual block content with boost 4;
- related tag names with boost 2.

Use PostgreSQL's language-neutral `simple` search configuration for exact
Russian, English, and mixed-language token matching. Search results use
Wagtail relevance ordering plus its `-pk` tie-break. SQLite FTS5 is a
local/test fallback whose ranking is not treated as PostgreSQL verification.

Do not add Elasticsearch or OpenSearch for the first version.

## Authentication and users

django-allauth provides Google and GitHub login.

Rules:

- reading is anonymous;
- commenting and reactions require authentication;
- provider scopes are minimal;
- provider tokens are discarded when no longer needed;
- successful login returns the user to the original route and pending action;
- the site owner is an administrator;
- the user and permission model must allow additional authors later;
- banned users retain historical content but cannot mutate public data.

Session cookies are issued by Django. Same-origin routing avoids CORS and allows
standard CSRF protection.

## Discussions

Comments use Slack-style threads rather than an unbounded Reddit tree.

- A post has top-level comments.
- A top-level comment may be a thread root.
- Replies remain at one visual depth.
- A reply may identify another participant through `reply_to_user`.
- Authors can edit and soft-delete their own comments.
- Soft-deleted roots retain their replies.
- Administrators can hide comments and ban users.

The `Comment` model contains:

- post foreign key;
- author foreign key;
- optional thread-root foreign key;
- optional reply-to-user foreign key;
- body;
- created, updated, edited, and deleted timestamps;
- moderation state.

User-provided arbitrary HTML is not accepted.

`post`, `author`, `thread_root`, `reply_to_user`, and moderation identity use
concrete foreign keys. Post and user identity deletion is protected while
comments exist, and a root with replies cannot be hard-deleted through the
normal API or admin UI. Database constraints enforce self-root, reply-shape,
and moderation-shape invariants; the transactional discussions service also
enforces cross-row rules that a root is top-level and shares the reply's post.

Top-level comments use a stable newest-first cursor; replies use a stable
oldest-first cursor and always point directly to their top-level root. Replying
to a reply derives `reply_to_user` from the selected target and does not create
another visual or persistence depth.

Comment mutations use Django `SessionAuthentication`, normal same-origin CSRF,
and a database-backed fixed-window limiter keyed by `(user, scope)`. A unique
row per create/reply or edit/delete scope is locked transactionally, avoiding
the cross-process and non-atomic behavior of DRF's local-memory throttle.

## Reactions

Unicode emoji reactions are supported on posts and comments, including replies.

Use two concrete tables:

- `PostReaction`;
- `CommentReaction`.

Each table has a unique constraint on target, user, and normalized emoji key.
Concrete relations preserve foreign-key integrity and predictable queries.

Users may add several different reactions to the same target. Repeating the same
reaction toggles it off. Reactions do not rank content.

Custom uploaded emoji are deferred.

## Email subscriptions

Subscriptions do not require an application account.

The flow includes:

- double opt-in;
- idempotent publication delivery;
- unsubscribe token;
- bounce and complaint processing;
- administrative visibility.

Use:

- `Subscriber`;
- `EmailOutbox`;
- `EmailDelivery`.

The database outbox is durable. A separate worker claims and delivers pending
messages. The provider is accessed through an adapter; Resend is the initial
choice, not a permanent domain dependency.

Do not self-host SMTP.

## Next.js frontend

Next.js owns all public presentation.

Use Server Components for:

- feed;
- bridge;
- post content;
- metadata.

Use Client Components only where browser interaction is required:

- login state;
- search controls;
- comments;
- thread panels;
- reactions;
- subscription forms.

Public routes:

- `/`;
- `/posts/[slug]`;
- `/bridge`.

### Responsive behavior

The public interface is mobile-first.

Required reference viewports:

- 375x812;
- 768x1024;
- 1440x900;
- 1920x1080.

Essential actions must not depend on hover. Touch targets should be about 44 px.
Mobile threads use a full-screen layer with the root pinned above and the reply
composer pinned below. Desktop may use a side panel.

## Preview and caching

Headless preview uses a signed Wagtail-to-Next.js flow and Next.js Draft Mode.
Preview endpoints must:

- expire;
- reject tampering;
- expose only the requested revision;
- avoid polluting the public cache.

Publishing and unpublishing trigger signed on-demand revalidation in Next.js.
At the initial single-instance scale, no distributed cache is required.

### Milestone 3 content boundary

The application-owned DRF contract is versioned at `/api/v1/`. Public posts use
one visibility service that requires live, public, published, due, and
not-expired content. StreamField data is a typed discriminated union rather
than Wagtail's internal representation. Responsive image filters are fixed at
widths 480, 960, and 1440.

`wagtail-headless-preview` 0.9.0 integrates the Wagtail editor, but the
application does not use its token as authorization. Django copies the package
snapshot into an immutable project record and issues an opaque
`TimestampSigner` credential with a default 600-second TTL. Wagtail transfers
it to Next.js through a short-lived HttpOnly cookie. The Next.js snapshot cookie
is scoped to `/posts`, so it is not sent to Django's public content API.

Publication lifecycle signals write cache events to a database outbox in the
same transaction as the Wagtail state change. Delivery happens after commit and
can be retried by management command. Requests use HMAC-SHA256 over the Unix
timestamp and exact raw JSON body. Next.js derives all tags and paths from a
strict semantic payload.

The exact Next.js routes `/api/draft`, `/api/draft/disable`, and
`/api/revalidate` are frontend-owned exceptions that future Nginx configuration
must match before the generic `/api/*` Django route. This exception does not
move application data ownership out of Django.

## Media

Wagtail manages image metadata and renditions. Original objects live in
S3-compatible storage.

Requirements:

- validated MIME type and file size;
- private upload credentials;
- stable public rendition URLs;
- responsive dimensions;
- alt text;
- separate staging and production storage;
- lifecycle and backup policy.

## Runtime and deployment

Docker Compose services:

- `nginx`;
- `next`;
- `django`;
- `worker`.

PostgreSQL and S3 may be external services.

Staging and production use:

- separate Compose projects;
- separate databases;
- separate media storage;
- separate OAuth applications;
- separate runtime secrets.

Do not hard-code shared `container_name` or Docker network names.

CI builds immutable Django and Next.js images for a git SHA. Staging deploys
automatically. Production manually promotes the exact image SHAs already tested
on staging.

## Security

At minimum:

- secure, HTTP-only, same-site session cookies;
- CSRF on every state-changing browser request;
- output escaping and safe rich-content rendering;
- authorization checks in Django, never only in Next.js;
- rate limits for OAuth, comments, reactions, and subscriptions;
- upload limits and type validation;
- CSP and standard security headers;
- protection against open redirects;
- secret values only in GitHub Environments or runtime secret files;
- no secrets in logs.

## Verification strategy

Backend:

- unit tests for models and constraints;
- API integration tests;
- permission and moderation tests;
- migration tests from an empty database;
- concurrency tests for reactions and delivery idempotency.

Frontend:

- component tests for interactive behavior;
- Playwright tests for critical reader flows;
- responsive and accessibility checks;
- server-rendering and metadata checks.

End-to-end:

- anonymous reading;
- Google and GitHub login;
- comment, reply, edit, and delete;
- reaction toggle;
- preview and scheduled publication;
- subscription, confirmation, delivery, and unsubscribe;
- staging-to-production promotion.

## Deliberately deferred

- visual redesign beyond functional responsive foundations;
- custom emoji;
- push notifications;
- Activity / Notification Center;
- native mobile applications;
- multiple active authors;
- GraphQL;
- Redis and Celery;
- Elasticsearch/OpenSearch.
