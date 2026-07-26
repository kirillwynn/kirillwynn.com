# Implementation status

Last updated: 2026-07-26

Integration branch: `rewrite/wagtail-next`

Overall state: foundation planning

## Current repository state

- The `main` branch contains the legacy Flask/React implementation.
- The legacy database and Alembic history are experimental.
- The new Django/Wagtail and Next.js application has not been scaffolded yet.
- Existing GitHub Actions, Nginx configuration, S3 utilities, social icons, and
  deployment secrets are reference material for the rebuild.
- The private product specification remains in the local Obsidian vault and is
  not committed.

## Completed

- [x] Product functionality agreed with the owner.
- [x] Target stack selected.
- [x] Same-origin service boundaries selected.
- [x] Slack-style threads selected.
- [x] Unicode reactions selected instead of likes/dislikes.
- [x] Mobile authoring excluded from the first version.
- [x] Local Obsidian product specification expanded.
- [x] Rebuild integration branch created.
- [x] Repository-level Codex instructions added.
- [x] Initial architecture document added.
- [x] Initial architecture ADR added.
- [x] Cross-session development workflow added.

## Active milestone

Milestone 1: repository foundation and clean application skeleton.

### Next recommended session

Scope:

1. Inventory reusable legacy assets and infrastructure.
2. Define the final `backend/`, `frontend/`, and `infra/` layout.
3. Scaffold Django 5.2 and Wagtail 7.4.
4. Create the custom user model before the first migration.
5. Add environment-based local settings.
6. Add a minimal backend healthcheck.
7. Add formatting, linting, and initial tests.

Out of scope for that session:

- Next.js UI;
- content models;
- OAuth providers;
- comments and reactions;
- deployment changes;
- deletion of legacy reference files that have not been inventoried.

### Exit criteria

- Django starts locally with an explicit development configuration.
- Wagtail Admin is mounted at `/cms/`.
- The custom user model is included in the clean baseline migration.
- Tests run from a documented command.
- No secrets are committed.
- Legacy production remains unaffected.
- This status file and the local Obsidian checklist are updated.

## Milestone queue

- [ ] Milestone 1 — repository foundation and Django/Wagtail skeleton.
- [ ] Milestone 2 — content pages, StreamField blocks, tags, media, revisions.
- [ ] Milestone 3 — REST content API, preview, and cache revalidation.
- [ ] Milestone 4 — Next.js shell, Feed, post renderer, and Bridge.
- [ ] Milestone 5 — Google/GitHub OAuth and session integration.
- [ ] Milestone 6 — comments and Slack-style threads.
- [ ] Milestone 7 — post and comment reactions.
- [ ] Milestone 8 — PostgreSQL search and tag filtering.
- [ ] Milestone 9 — email subscriptions and durable outbox worker.
- [ ] Milestone 10 — isolated staging/production infrastructure.
- [ ] Milestone 11 — end-to-end hardening and functional launch.
- [ ] Milestone 12 — visual design and polish.

## Known risks

- Wagtail headless preview requires deliberate integration with Next.js Draft
  Mode.
- OAuth callbacks and credentials must be separate for staging and production.
- Current Docker Compose names collide if both environments run on one server.
- The current deployment workflow rebuilds production rather than promoting an
  already-tested staging image.
- Legacy migrations contain resets and multiple heads and should not be reused
  as the new baseline.
- Email DNS records and provider credentials do not exist in the current
  workflow.

## Decisions pending

No blocking product decisions are currently open.

Implementation-level choices should be recorded in a new ADR when they affect:

- service boundaries;
- persistence or migration strategy;
- authentication/session architecture;
- queue infrastructure;
- public API shape;
- deployment topology;
- a deliberately deferred dependency.

## Last verification

Documentation-only setup. No application tests were run because no new
application code was introduced.
