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
- [ADR 0001: Django/Wagtail and Next.js](docs/decisions/0001-django-wagtail-nextjs.md)
- [Codex project instructions](AGENTS.md)

## Current state

The first backend foundation is available under `backend/django/`:

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
- `http://localhost:8000/cms/`
- `http://localhost:8000/django-admin/`

Create a local administrator after the services are running:

```bash
docker compose -f compose.dev.yml exec django python manage.py createsuperuser
```

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

`uv.lock` is the complete development lock. `requirements.lock` is an exported,
fully pinned production dependency set used by the Django container. When
dependencies change, regenerate both intentionally:

```bash
cd backend/django
uv lock
uv export --frozen --no-dev --no-editable --no-emit-project --no-hashes \
  --output-file requirements.lock
```
