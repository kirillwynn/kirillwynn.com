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
- Google and GitHub login
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
- [Content API contract](docs/api-contract.md)
- [ADR 0001: Django/Wagtail and Next.js](docs/decisions/0001-django-wagtail-nextjs.md)
- [ADR 0002: Content API, preview, and revalidation](docs/decisions/0002-content-api-preview-revalidation.md)
- [ADR 0003: Concrete Unicode reaction contract](docs/decisions/0003-unicode-reaction-contract.md)
- [Codex project instructions](AGENTS.md)

## Current state

Milestones 1–8 are available under `backend/django/` and `frontend/next/`:

- Python 3.12.13;
- Django 5.2.16 LTS;
- Wagtail 7.4.2 LTS at `/cms/`;
- Django REST Framework 3.17.1;
- PostgreSQL configuration through environment variables;
- a custom `users.User` model in the initial project migration;
- environment-specific local, test, and production settings;
- `/api/health/`, Django Admin, and Wagtail Admin smoke coverage;
- singleton blog index and structured post authoring with normalized tags;
- SEO/Open Graph metadata and all 13 first-version StreamField block types;
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
- a server-rendered URL-driven searchable/tag-filtered Feed with accessible
  controls and pagination, plus full post pages with all 13 typed StreamField
  renderers;
- responsive 480/960/1440 rendition rendering, accessible content tables,
  read-only checklists, and server-rendered syntax highlighting with a safe
  plain-text fallback;
- per-post canonical, SEO, Open Graph article, and Draft Mode noindex metadata;
- a responsive Bridge page with the eight legacy profile links and reused SVG
  assets;
- private immutable Draft Mode rendering and HMAC revalidation;
- classic Google/GitHub OAuth through django-allauth 65.18.0;
- Django database-backed sessions, same-origin cookies, and standard CSRF;
- `/api/me/`, CSRF-protected `POST /api/auth/logout/`, `/login`, `/account`,
  and the authenticated header menu;
- plain-text post comments and one-level Slack-style threads with cursor
  pagination, soft deletion, moderation tombstones, protected identities, and
  database-backed per-user mutation limits;
- concrete post/comment Unicode reactions with transactional target locks,
  grouped viewer state, private cursor-paginated participants, and Wagtail
  quick-reaction settings;
- accessible post/comment/reply reaction pills, a lazy local Unicode picker,
  bounded recent emoji, optimistic rollback, and confirmation-based OAuth
  continuation;
- an accessible desktop thread drawer and mobile full-screen thread layer with
  pinned root/composer, focus restoration, query-string navigation, and
  sessionStorage-backed pending OAuth drafts;
- verified-email provider linking without retained provider tokens, JWT,
  Auth.js, or browser-stored session tokens;
- locked production and development dependencies.

Existing files under `backend/app/`, `frontend/`, `docker/`, `nginx/`, and the
legacy deployment workflows remain reference material. The legacy
`docker-compose.yml` is separate from the new `compose.dev.yml`.

Do not use legacy behavior as the product specification. Check
`docs/implementation-status.md` before starting work.

## Local backend with Docker

Docker Compose is the primary local path because it provides PostgreSQL:

```bash
cp .env.example .env
docker compose -f compose.dev.yml up --build
```

The Django container waits for PostgreSQL, applies migrations, and starts at
`http://localhost:8000`. Useful routes:

- `http://localhost:8000/api/health/`
- `http://localhost:3000/login`
- `http://localhost:3000/account`
- `http://localhost:8000/cms/`
- `http://localhost:8000/django-admin/`

Create a local administrator after the services are running:

```bash
docker compose -f compose.dev.yml exec django python manage.py createsuperuser
```

OAuth applications are optional for local content development. When configured,
set the four `GOOGLE_OAUTH_*` and `GITHUB_OAUTH_*` variables from
`.env.example`; unavailable providers remain disabled in the UI. Browser flows
must start on `http://localhost:3000`, whose fixed rewrites preserve Django
cookies and `Set-Cookie` headers. See [OAuth setup](docs/oauth-setup.md) for
callbacks, scopes, staging/production isolation, and owner promotion.

Stop the stack without deleting its database volume:

```bash
docker compose -f compose.dev.yml down
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

- `GET /api/v1/reactions/config/`;
- `GET /api/v1/posts/<unicode-slug>/reactions/`;
- `POST /api/v1/posts/<unicode-slug>/reactions/toggle/`;
- `GET /api/v1/comments/<id>/reactions/`;
- `POST /api/v1/comments/<id>/reactions/toggle/`;
- exact post/comment participant endpoints documented in
  [the API contract](docs/api-contract.md).

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

- `/` — the server-rendered URL-driven public Feed with accessible search,
  tag filters, and pagination;
- `/posts/[slug]` — public and private Draft Mode post rendering;
- `/bridge` — the eight approved profile links and team labels;
- `/api/draft` and `/api/draft/disable`;
- signed `POST /api/revalidate`;
- `/login` and `/account` with Google/GitHub POST initiation and provider
  connection state;
- client-side comments below public posts and a responsive Slack-style thread
  layer; comments are deliberately omitted from Draft Mode;
- post, comment, and reply reactions with quick actions, local lazy picker,
  participants, recent emoji, and no Draft Mode reaction UI;
- a keyboard/touch accessible current-user menu and CSRF-protected logout;
- loading, upstream error, empty, and not-found states.

OAuth initiation is a normal CSRF-protected browser POST to django-allauth. The
OAuth redirect is never sent through client-side fetch.

Every Feed list/search/tag-count fetch uses only the `posts` cache tag. Public
post details use only `post-slug:<slug>`. Draft snapshots are resolved
server-to-server with `cache: "no-store"` and never enter the public cache.

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
