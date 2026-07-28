# ADR 0005: One edge and isolated application Compose projects

Status: accepted

Date: 2026-07-27

## Context

Staging and production run on one server but must not share application state.
The legacy Flask/Vite stack uses fixed names and rebuilds during deployment, so
it cannot safely run both environments or prove production uses the release
tested on staging.

## Decision

Run three Compose projects:

```text
Internet
   |
kirillwynn-edge (80/443 and TLS)
   |                         |
staging edge network         production edge network
   |                         |
staging app project          production app project
  - Django/Gunicorn            - Django/Gunicorn
  - Next standalone            - Next standalone
  - one worker                 - one worker
  - PostgreSQL                 - PostgreSQL
  - private network/volumes    - private network/volumes
```

The edge project is the only owner of host ports 80 and 443. Each application
project owns its PostgreSQL and Next cache volumes and three private networks:
an `internal: true` database network, an `internal: true` application network,
and a non-publishing egress bridge. PostgreSQL joins only the database network.
Next cannot reach PostgreSQL at the network layer. Django and the worker join
the database/application/egress boundaries; Next joins
application/egress/edge. PostgreSQL and worker never join edge. The edge
project owns both environment-qualified edge networks even before either
application exists. No service uses `container_name`.

The egress bridges publish no ports and are separate per environment. They are
the only application path to S3, OAuth, Resend, and other required outbound
HTTP services; database/application networks cannot route externally.

### Trust boundaries and same-origin routing

The browser trusts one public origin per environment. Edge terminates TLS,
replaces rather than appends the inbound forwarding chain, and routes exact
Next.js Draft Mode/revalidation exceptions before Django API prefixes. Django
alone owns sessions, CSRF, OAuth, CMS, administration, and `/api/v1/`. Cookies
and `Set-Cookie` are not rewritten. Staging Basic Auth applies except to ACME
and the exact Resend webhook; that webhook still requires its Svix signature
and replay window.

Uploaded media never uses a production container filesystem. Each environment
has a distinct S3 bucket/prefix, credentials, and public origin. `/media/` at
edge returns 404. Static files are collected into the immutable Django image
and served from that output through WhiteNoise; edge applies long caching only
to manifest-hashed names.

### Images and promotion

CI builds Django, Next.js, and edge once for a full Git SHA and records registry
digests in a validated release manifest. Django web and worker use the same
digest. Next reads `PUBLIC_SITE_URL` and the internal Django origin only during
dynamic server rendering, so staging and production run the same bytes.

Staging consumes the manifest automatically only when
`STAGING_DEPLOY_ENABLED=true`. Successful smoke checks create a staging
attestation. Production is a manual GitHub Environment deployment and accepts
only the same attested manifest; it never rebuilds. The shared edge is a
host-wide component: staging checks its exact digest with a one-shot,
non-port-publishing `nginx -t`, while production replaces it only under
approval after the staging app smoke/attestation. Ordinary staging app
replacement leaves the live edge running.

Nginx 1.29 uses Docker DNS (`127.0.0.11`) with bounded resolver timeouts,
shared upstream zones, and `server ... resolve`. Edge therefore starts when
one or both application environments are absent, returns a bounded 502 only
for the unavailable host, and follows environment-qualified Django/Next
replacement without retaining a removed container IP or restarting edge.
Candidate `nginx -t` remains mandatory before edge replacement.

### Migration, rollout, and rollback

Release order is validate → backup → pull exact app digests → one-shot
`migrate --noinput` with the new Django digest → bounded Compose `--wait` →
Django readiness/Next health/worker heartbeat/provider-egress/exact-image
checks → public smoke → active-state commit. A failed gate leaves the candidate
pending or failed and never marks its manifest active. Schema changes must be
expand/contract and compatible with the previous digest. This initial
single-replica model expects brief service downtime; it does not claim zero
downtime.

First production deploy has an explicit exception only to the meaning of
"existing database": with no active production state it starts the pinned
PostgreSQL service through the database-only Compose contract, takes and
verifies an empty initial backup, and only then migrates or starts application
services. Every later deploy backs up the active database before migration.

Application rollback selects the previous compatible manifest and restarts its
Django/Next digests without rebuilding. Migrations are never reversed
automatically. A reverse migration requires separate review, a fresh verified
backup, and a scratch restore rehearsal.

### Worker ownership

Each environment runs one worker by default. It independently schedules bounded
`publish_scheduled_pages`, `process_revalidation_outbox`,
`process_email_outbox`, and `reconcile_email_webhooks` calls. Per-task failures
back off without stopping other tasks. SIGTERM is graceful and an atomic
heartbeat drives health. Existing commands keep provider/network calls outside
claim transactions.

### Backup, restore, and secrets

Backups and restores use a database-only Compose contract that cannot
interpolate Django or Next images. It targets the same named PostgreSQL volume
and database network as the application contract. Backups use custom-format
`pg_dump`, UTC/release metadata, SHA-256, and `pg_restore --list`. Restore
authenticates the required sidecar shape, source environment, filename, and
checksum before `createdb`, creates only a new `restore_*` scratch database,
and never drops a database. Production retains typed confirmation. S3 media
protection uses environment-specific provider versioning/lifecycle.

GitHub Environments deliver values to separate raw Compose env files:
control (only names, paths, aliases, sequence, and pinned images), PostgreSQL
(DB/user/password), Django web, minimal worker, and Next
(`PUBLIC_SITE_URL`, `DJANGO_API_URL`, `REVALIDATION_SECRET`). Docker Compose
2.30 or newer is required for `env_file.format: raw`. Repository scripts reject
missing, extra, multiline, NUL, oversized, or cross-environment values while
preserving allowed single-line bytes including dollar signs, `${...}`, `#`,
quotes, backslashes, and spaces. Secrets never participate in Compose
interpolation.

Each release installs a versioned infrastructure bundle, manifest, and
role-scoped runtime files under `/srv/kirillwynn/`. Per-environment state keeps
the current and previous manifests plus active release evidence; backup
metadata is retained with dumps. Staging and production jobs share one GitHub
concurrency group and one server `flock`; pending state blocks a second
rollout, and a monotonic deployment sequence prevents an older completed
`main` workflow from rolling staging back. Rollback consumes the previous
durable bundle/digests, takes a fresh backup, never reverses migrations, and is
subject to the same health/public-smoke activation boundary.

### No Redis or Celery

The bounded workload is already durable in PostgreSQL outboxes. Redis/Celery
would add persistence, backup, monitoring, and failure domains without solving
a measured throughput issue. Revisit only when queue latency or parallelism
cannot be met by bounded relational claims.

## Consequences

Staging and production have no port, network, alias, volume, database, S3,
OAuth, Resend, or secret collisions. Promotion is auditable and build-free.
The tradeoffs are brief single-replica rollout downtime, explicit shared-edge
coordination, and operational PostgreSQL/S3 backup ownership.
