# kirillwynn.com

Personal publishing website for Kirill Wynn.

The repository contains a legacy Flask/Vite implementation and the new
Django/Wagtail backend being built on `rewrite/wagtail-next`. The legacy
application remains unchanged as reference material and is not part of the new
local development stack.

## Target stack

- Django 5.2 LTS
- Wagtail 7.4 LTS
- Django REST Framework
- django-allauth
- PostgreSQL
- Next.js App Router
- React and TypeScript
- Tailwind CSS
- Nginx and Docker Compose
- S3-compatible media storage

## Product summary

- `/` — searchable feed of published posts
- `/posts/<slug>` — full post, reactions, comments, and Slack-style threads
- `/bridge` — links to external profiles
- `/subscriptions/` — anonymous double-opt-in subscription entry
- Local email/password accounts plus Google and GitHub login
- Required unique public nicknames and verified-email interaction boundary
- Wagtail desktop authoring with revisions, preview, and scheduling
- Emoji reactions on posts, comments, and replies
- Double-opt-in email subscription
- Isolated staging and production deployments

The complete product specification is intentionally kept outside the repository
in the author's local Obsidian vault:

`~/.wisdom/wisdom/Projects/kirillwynn.com.md`

Do not copy that note into the repository.

## Documentation

- [Architecture](docs/architecture.md)
- [Implementation status](docs/implementation-status.md)
- [Development workflow](docs/development-workflow.md)
- [Editorial workflow](docs/editorial-workflow.md)
- [Content API contract](docs/api-contract.md)
- [ADR 0001: Django/Wagtail and Next.js](docs/decisions/0001-django-wagtail-nextjs.md)
- [ADR 0002: Content API, preview, and revalidation](docs/decisions/0002-content-api-preview-revalidation.md)
- [ADR 0003: Concrete Unicode reaction contract](docs/decisions/0003-unicode-reaction-contract.md)
- [ADR 0004: Email subscriptions, outbox, and Resend](docs/decisions/0004-email-subscriptions-outbox-resend.md)
- [ADR 0005: Isolated Compose deployment](docs/decisions/0005-isolated-compose-deployment.md)
- [ADR 0006: Manifest-managed custom reaction catalog](docs/decisions/0006-manifest-managed-reaction-catalog.md)
- [ADR 0007: Editorial dates and publication-email decisions](docs/decisions/0007-editorial-dates-and-publication-email-decision.md)
- [ADR 0008: Local identity, nicknames, and auth email](docs/decisions/0008-local-identity-nicknames-and-auth-email.md)
- [ADR 0009: Public navigation, cache, and infinite Feed](docs/decisions/0009-public-navigation-cache-and-infinite-feed.md)
- [ADR 0010: Wagtail writing experience](docs/decisions/0010-wagtail-writing-experience.md)
- [Reaction catalog asset runbook](docs/reaction-catalog-runbook.md)
- [Email provider and DNS setup](docs/email-setup.md)
- [Deployment and rollback](docs/deployment-runbook.md)
- [Runtime environment matrix](docs/environment-matrix.md)
- [Backup and restore](docs/backup-restore-runbook.md)
- [Staging activation](docs/staging-activation-checklist.md)
- [Production promotion](docs/production-promotion-checklist.md)
- [Codex project instructions](AGENTS.md)

## Current state

The implemented rewrite is available under `backend/django/`,
`frontend/next/`, and `infra/`:

- Python 3.12.13;
- Django 5.2.16 LTS;
- Wagtail 7.4.2 LTS at `/cms/`;
- Django REST Framework 3.17.1;
- PostgreSQL configuration through environment variables;
- a custom `users.User` model in the initial project migration;
- environment-specific local, test, and production settings;
- `/api/health/`, Django Admin, and Wagtail Admin smoke coverage;
- a permission-aware `New post` shortcut and centred writing-first Wagtail
  editor with compact native Draftail toolbars for the dynamically resolved
  singleton Blog index;
- structured post authoring with normalized tags, revision-aware archive dates,
  durable first-publication newsletter decisions, and clear workflow
  documentation;
- SEO/Open Graph metadata and all 13 stable first-version StreamField block
  types with grouped, described chooser entries;
- backend draft preview with image renditions, revisions, rollback, and
  publication scheduling coverage;
- anonymous live-only `/api/v1/posts/` list and slug detail endpoints;
- PostgreSQL-backed Wagtail full-text search over weighted title, excerpt,
  textual body content, and tag names;
- combined `q` and exact Unicode `tag` post filtering plus live-only
  `/api/v1/tags/` counts;
- a stable version 1.0 serializer for all 13 body blocks, tags, metadata, and
  fixed 480/960/1440 image renditions;
- immutable, ten-minute headless preview snapshots integrated through
  `wagtail-headless-preview` 0.9.0;
- signed cache revalidation backed by a durable database outbox and retry
  command;
- Unicode post slugs across public detail, preview, and signed revalidation;
- public-origin canonical/media URLs through `PUBLIC_SITE_URL`, with
  origin-independent relative pagination links;
- a public Next.js 16.2.11 App Router shell with Tailwind CSS 4.3.3;
- an SSR-first searchable Feed with persistent client navigation, infinite
  page loading, accessible manual fallback, browser-history restoration, and
  no visible tag or page controls, plus full post pages with all 13 typed
  StreamField renderers;
- responsive 480/960/1440 rendition rendering, accessible content tables,
  read-only checklists, and server-rendered syntax highlighting with a safe
  plain-text fallback;
- per-post canonical, SEO, Open Graph article, and Draft Mode noindex metadata;
- a responsive icon-only Bridge grid with eight accessible legacy profile
  links and reused SVG assets, plus the same centered team-only footer used by
  every public route;
- private immutable Draft Mode rendering and HMAC revalidation;
- classic Google/GitHub OAuth through django-allauth 65.18.0;
- Django database-backed sessions, same-origin cookies, and standard CSRF;
- `/api/me/`, CSRF-protected `POST /api/v1/auth/logout/`, `/login`, `/account`,
  and the authenticated header menu;
- plain-text post comments and one-level Slack-style threads with cursor
  pagination, soft deletion, moderation tombstones, protected identities, and
  database-backed per-user mutation limits;
- concrete post/comment catalog reactions with transactional target locks,
  grouped descriptors/viewer state, private cursor-paginated participants,
  preserved legacy Unicode rows, and Wagtail quick-reaction settings;
- accessible compact post/comment/reply reaction pills, lazy static/animated
  assets, a persistent prefetched searchable custom picker with dismissable
  desktop/mobile layers, bounded catalog-ID recents, reduced-motion poster
  enforcement, optimistic rollback, and confirmation-based OAuth continuation;
- an accessible desktop thread drawer and mobile full-screen thread layer with
  pinned root/composer, focus restoration, query-string navigation, and
  sessionStorage-backed pending OAuth drafts;
- verified-email provider linking without retained provider tokens, JWT,
  Auth.js, or browser-stored session tokens;
- canonical email/password signup and login, mandatory email verification,
  reset/set/change password flows, and OAuth profile completion;
- permanent Unicode nickname claims with a 30-day change cooldown, one
  authoritative public display helper, and Wagtail-owner post attribution;
- a separate durable auth-email outbox whose provider I/O remains worker-only;
- anonymous double-opt-in subscriptions with canonical case-insensitive email
  identity, versioned 48-hour confirmation credentials, revocable unsubscribe,
  and non-enumerating CSRF-protected APIs;
- durable confirmation/publication outbox events, immutable publication
  audience cutoffs, irreversible queued/suppressed first-publication decisions,
  unique per-reader deliveries, bounded PostgreSQL claims, stale reclaim,
  capped exponential retry, and terminal failure visibility;
- exact-byte deterministic/Resend provider adapters, immutable adapter
  contract/version and idempotency namespace, provider-independent
  `EMAIL_FROM_ADDRESS`, multipart templates, Resend idempotency keys, RFC 8058
  one-click headers, and delivery, bounce/complaint webhook handling through
  exact raw-body Svix verification;
- one accessible `/subscriptions/` entry form and explicit
  noindex/no-referrer confirmation and unsubscribe pages with no Draft Mode
  requests or browser credential persistence;
- locked production and development dependencies;
- non-root Django/worker and Node 24 standalone images plus a shared Nginx
  edge image;
- isolated environment projects, databases, volumes, networks, aliases, S3
  and provider namespaces, healthchecks, and log limits;
- build-once manifests, gated staging, manual staging-attested production
  promotion, backup gate, and digest rollback;
- a graceful bounded worker and safe PostgreSQL backup/restore scripts.

Existing Flask/Vite source under `backend/app/`, legacy `frontend/`,
`docker/Dockerfile.app`, and `nginx/` remains reference material. Active root
Compose and GitHub workflows no longer build or deploy Flask/Vite.

Do not use legacy behavior as the product specification. Check
`docs/implementation-status.md` before starting work.

## Local backend with Docker

Docker Compose is the primary local path because it provides PostgreSQL:

```bash
cp .env.example .env
docker compose up --build
```

The Django container waits for PostgreSQL, applies migrations, and starts at
`http://localhost:8000`. Useful routes:

- `http://localhost:8000/api/health/`
- `http://localhost:3000/login`
- `http://localhost:3000/signup`
- `http://localhost:3000/account`
- `http://localhost:3000/account/profile`
- `http://localhost:8000/cms/`
- `http://localhost:8000/django-admin/`

Create a local administrator after the services are running:

```bash
docker compose exec django python manage.py createsuperuser
```

OAuth applications are optional for local content development. When configured,
set the four `GOOGLE_OAUTH_*` and `GITHUB_OAUTH_*` variables from
`.env.example`; unavailable providers remain disabled in the UI. Browser flows
must start on `http://localhost:3000`, whose fixed rewrites preserve Django
cookies and `Set-Cookie` headers. See [OAuth setup](docs/oauth-setup.md) for
callbacks, scopes, staging/production isolation, and owner promotion.

Stop the stack without deleting its database volume:

```bash
docker compose down
```

## Local backend without Docker

Install [uv](https://docs.astral.sh/uv/), provide a reachable PostgreSQL
database through the variables documented in `.env.example`, then run:

```bash
cd backend/django
uv python install
uv sync --frozen
uv run python manage.py migrate
uv run python manage.py runserver
```

Public content routes:

- `http://localhost:8000/api/v1/posts/`;
- `http://localhost:8000/api/v1/posts/?q=django&tag=python`;
- `http://localhost:8000/api/v1/tags/`;
- `http://localhost:8000/api/v1/posts/<slug>/`;
- `http://localhost:8000/api/v1/preview/resolve/` (server-to-server preview
  resolution only).

Discussion routes:

- `GET/POST /api/v1/posts/<unicode-slug>/comments/`;
- `GET /api/v1/comments/<id>/thread/`;
- `POST /api/v1/comments/<id>/replies/`;
- `PATCH/DELETE /api/v1/comments/<id>/`.

Reaction routes:

- `GET /api/v1/reactions/config/` (deprecated, rollback-only; the current
  public UI does not request it);
- `GET /api/v1/posts/<unicode-slug>/reactions/`;
- `POST /api/v1/posts/<unicode-slug>/reactions/toggle/`;
- `GET /api/v1/comments/<id>/reactions/`;
- `POST /api/v1/comments/<id>/reactions/toggle/`;
- exact post/comment participant endpoints documented in
  [the API contract](docs/api-contract.md).

Subscription routes:

- `POST /api/v1/subscriptions/`;
- `POST /api/v1/subscriptions/confirm/`;
- `POST /api/v1/subscriptions/unsubscribe/`;
- `POST /api/v1/subscriptions/unsubscribe/one-click/`;
- `POST /api/v1/email/webhooks/resend/`.

Local account routes (all exact, JSON-only mutation paths):

- `POST /api/v1/auth/signup/`;
- `POST /api/v1/auth/login/`;
- `POST /api/v1/auth/verify-email/` and
  `POST /api/v1/auth/verify-email/resend/`;
- `POST /api/v1/auth/password/reset/` and
  `POST /api/v1/auth/password/reset/confirm/`;
- `POST /api/v1/auth/password/set/` and
  `POST /api/v1/auth/password/change/`;
- `PATCH /api/v1/auth/profile/`;
- `POST /api/v1/auth/logout/`.

The browser uses the versioned paths so a staging-only application rollout can
traverse the already-active shared `/api/v1/` boundary without replacing the
shared edge. Exact legacy `/api/auth/` aliases remain for application rollback;
neither namespace has a wildcard auth proxy.

Comment mutations use Django sessions, normal CSRF, and the per-user fixed
windows configured by the four `COMMENT_*_RATE_LIMIT_*` environment values.
Defaults are 10 creates/replies and 30 edits/deletes per 60 seconds. Comment
responses are always `private, no-store` and never enter the public post cache.
Reaction toggles default to 60 per 60 seconds through the two
`REACTION_TOGGLE_RATE_LIMIT_*` values. Reaction responses use the same
private/no-store viewer boundary.

`PUBLIC_SITE_URL` is public configuration, not a secret. It defaults to
`http://localhost:3000` in local settings and is required in production as an
HTTP(S) origin without a path, query, or fragment. The backend uses it for
fallback canonical URLs and local media/rendition URLs even when Next.js calls
Django through an internal host. Absolute S3/CDN URLs and authored canonical
URLs are preserved. Pagination links are relative API URLs. Production search
uses Wagtail's `wagtail.search.backends.database` over PostgreSQL with the
language-neutral `simple` configuration. SQLite FTS5 is only the
local/unit-test fallback and does not verify PostgreSQL ranking. Run
`uv run python manage.py update_index` after changing search fields or
deploying this initial search configuration.

Retry pending cache events:

```bash
cd backend/django
uv run python manage.py process_revalidation_outbox --limit 100
```

Process a bounded email batch:

```bash
cd backend/django
uv run python manage.py process_email_outbox --limit 25 --delivery-limit 100
```

Process the independent account-email outbox:

```bash
cd backend/django
uv run python manage.py process_auth_email_outbox --limit 25
```

Reconcile bounded early-arriving webhook state and retention:

```bash
cd backend/django
uv run python manage.py reconcile_email_webhooks --limit 100
```

The commands are safe to rerun and print counts without addresses, provider
payloads, or credentials. Production runs them through the one-instance
bounded worker in `infra/compose/application.yml`.
See [email setup](docs/email-setup.md) for Resend, SPF/DKIM/DMARC, webhook,
rotation, and worker scheduling steps.

Every production email adapter requires a normalized `EMAIL_FROM_ADDRESS`.
Every environment also requires a normalized, non-secret
`EMAIL_PROVIDER_IDEMPOTENCY_NAMESPACE` that changes with provider account or
environment, but stays fixed during API-key rotation inside that account.
Resend additionally requires only its API key and webhook secret. The bundled
memory adapter is for local/test use; another external adapter must declare a
stable contract identifier/serializer version and accept only the immutable
prepared bytes selected by its deterministic serializer.

The test suite uses an isolated SQLite database so fast checks do not require a
running PostgreSQL service:

```bash
cd backend/django
uv run ruff format --check .
uv run ruff check .
uv run python manage.py check --settings=config.settings.test
uv run python manage.py makemigrations --check --dry-run --settings=config.settings.test
uv run pytest
```

## Next.js public frontend

Node.js 24 LTS and npm are required. The legacy Vite frontend remains unchanged.

```bash
cd frontend/next
cp .env.example .env.local
npm ci
npm run dev
```

The public frontend includes:

- `/` — the SSR-first public Feed with IME-safe client search, infinite loading,
  an accessible manual fallback, and no visible hashtags or page controls;
- `/posts/[slug]` — public and private Draft Mode post rendering;
- `/bridge` — an icon-only grid of eight accessible profile links; the shared
  footer on this and every other public route contains only the two team
  history rows;
- `/subscriptions/` — the only public subscription form; Feed and post pages
  link to it rather than embedding a form;
- `/api/draft` and `/api/draft/disable`;
- signed `POST /api/revalidate`;
- `/login`, `/signup`, `/account`, `/account/profile`, email verification,
  password reset confirmation, password set, and password change, with local
  forms plus Google/GitHub POST initiation and provider connection state;
- client-side comments below public posts and a responsive Slack-style thread
  layer; comments are deliberately omitted from Draft Mode;
- post, comment, and reply aggregate reactions with one picker trigger,
  explicit-activation participants, shared warm catalog/module caches, and no
  suggested/quick or Draft Mode reaction UI;
- a keyboard/touch accessible current-user menu and CSRF-protected logout;
- loading, upstream error, empty, and not-found states.

OAuth initiation is a normal CSRF-protected browser POST to django-allauth. The
OAuth redirect is never sent through client-side fetch.

Next.js Cache Components place Feed list/search/tag metadata and post detail in
explicit `"use cache"` scopes. Public scopes carry `posts`, detail slug, and
stable post-ID tags for signed publish/update/unpublish/expiry/rename
invalidation. Draft snapshots are resolved server-to-server with
`cache: "no-store"` and never enter the public cache. Viewer-specific auth,
comments, reactions, and participants remain private browser queries segmented
by authenticated identity.

`REVALIDATION_SECRET` must contain at least 32 UTF-8 bytes. Django and Next.js
reject a shorter runtime production value. Production preview cookies are
always Secure; local HTTP preview remains available without Secure cookies.

`PUBLIC_SITE_URL` is public server-rendering configuration rather than a
secret. It defaults to `http://localhost:3000` outside production and is
required in production as an HTTP(S) origin without a path, query, or fragment.
It is used for static-page metadata and must never be replaced with the
server-to-server `DJANGO_API_URL`.

`uv.lock` is the complete development lock. `requirements.lock` is an exported,
fully pinned production dependency set used by the Django container. When
dependencies change, regenerate both intentionally:

```bash
cd backend/django
uv lock
uv export --frozen --no-dev --no-editable --no-emit-project --no-hashes \
  --output-file requirements.lock
```
