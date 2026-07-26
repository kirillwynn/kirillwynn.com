# kirillwynn.com

Personal publishing website for Kirill Wynn.

The repository currently contains a legacy Flask implementation and is being
rebuilt on the `rewrite/wagtail-next` branch.

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

The existing `backend/`, `frontend/`, `docker/`, and `nginx/` directories belong
to the legacy Flask/React implementation. They remain available as a reference
until useful infrastructure, icons, and configuration have been intentionally
migrated.

Do not use legacy behavior as the product specification. Check
`docs/implementation-status.md` before starting work.
