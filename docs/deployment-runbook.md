# Deployment and rollback runbook

## Repository layout

- `backend/django/Dockerfile`: one non-root Django/worker image.
- `frontend/next/Dockerfile`: non-root Node 24 standalone image.
- `infra/docker/edge.Dockerfile`: shared Nginx-only edge image.
- `infra/compose/application.yml`: environment application project.
- `infra/compose/edge.yml`: one shared 80/443 project.
- `.github/workflows/ci.yml`: SQLite, PostgreSQL, frontend, image, Compose,
  Nginx, and container checks.
- `.github/workflows/build.yml`: build once, manifest, gated staging rollout.
- `.github/workflows/deploy-production.yml`: manual attested promotion.

## Release contract

The manifest contains a full source SHA and `django`, `next`, and `edge`
references pinned by `sha256`. Mutable `latest` and zero placeholders are
rejected. Django and worker use exactly the same image.

The runner packages only `infra/compose` and `infra/scripts` from the checked
out release SHA and executes that temporary bundle remotely. Deployment does
not trust or update a server-side Git checkout. Runtime values are transferred
separately through the fixed allowlist and the temporary directory is removed
on both success and failure.

Staging remains disabled until `STAGING_DEPLOY_ENABLED` is exactly `true`.
After activation, successful CI on `main` builds one set, migrates staging
once, rolls app services, checks the exact candidate edge digest with
`nginx -t` without publishing its ports, and records an attestation only after
smoke checks.

Production is manually dispatched with the full SHA and protected by the
`production` GitHub Environment. It downloads the existing manifest and
staging attestation, takes a verified backup, migrates once, and starts those
exact app digests. It then validates and replaces the shared edge with the
attested edge digest. It never invokes a build.

## Migration and rollback

Use expand/contract migrations compatible with the still-running prior app.
Order is pull → backup → `migrate --noinput` → Compose replacement →
readiness/smoke. A failed migration stops before replacement. CI only checks
migration drift; it never generates or commits migrations.

Rollback checklist:

1. identify the previous manifest and prove compatibility with current schema;
2. pause the worker if delivery behavior is involved;
3. restart the previous Django/Next digests;
4. do not reverse migrations automatically;
5. verify health, readiness, Feed, Bridge, CMS, login, and heartbeat;
6. record active manifest and incident.

A required reverse migration needs a fresh backup, scratch rehearsal, and
separate approval. Restoration never targets an existing database by default.

## Edge route contract

Next.js receives `/`, `/posts/*`, `/bridge`, `/login`, `/account`,
`/subscriptions/*`, `/_next/*`, and the exact `/api/draft`,
`/api/draft/disable`, and `/api/revalidate` routes. The last three are matched
before Django API prefixes. The internal Next liveness path is rejected at
edge.

Django receives exact `/api/health/`, `/api/readiness/`, `/api/me/`, and
`/api/auth/logout/`, plus `/api/v1/*`, `/accounts/*`, `/cms/*`, and
`/django-admin/*`. `/media/documents/*` is an explicit Wagtail redirect to S3;
other `/api/*` and `/media/*` return 404. `/static/*` is served from Django's
immutable collectstatic output, with edge immutable caching only for hashed
filenames.

Forwarded `Host`, `X-Forwarded-Host`, protocol, client IP, and forwarding chain
are set by edge. Client-supplied forwarding chains are discarded. No proxy
cache or cookie rewriting is configured. Wagtail uploads allow 25 MiB only
under `/cms/`; the default request limit is 1 MiB. Staging Basic Auth excludes
only ACME and exact `/api/v1/email/webhooks/resend/`.

## Shared edge and availability

Only `kirillwynn-edge` publishes 80/443. Staging app deployment does not restart
it; it tests the exact candidate in a one-shot no-port container. Manual
production promotion performs the host-wide replacement after that attestation
and a second `nginx -t`. Keep routes compatible with both active app versions.

One Django, Next, and worker replica per environment means Compose replacement
may cause a brief interruption. A zero-downtime/blue-green model is deferred
until server capacity and need justify a second replica.
