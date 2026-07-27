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
project owns its PostgreSQL and Next cache volumes, private network, and one
explicit edge network. PostgreSQL and worker never join an edge network.
Django and Next receive environment-qualified aliases. No service uses
`container_name`.

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

### Migration, rollout, and rollback

Release order is validate → pull digests → production backup → one-shot
`migrate --noinput` with the new Django digest → replace app services → health
and smoke. Schema changes must be expand/contract and compatible with the
previous digest. This initial single-replica model expects brief service
downtime; it does not claim zero downtime.

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

Backups use custom-format `pg_dump`, UTC/release metadata, and
`pg_restore --list`. Restore creates a new `restore_*` scratch database and
never drops a database. Production requires typed confirmation. S3 media
protection uses environment-specific provider versioning/lifecycle.

GitHub Environments deliver secrets to a bounded allowlist. Repository scripts
reject missing, extra, multiline, oversized, or cross-environment values,
write under `umask 077`, and atomically replace runtime files. Secrets are not
embedded in SSH program text, image layers, manifests, browser assets, or logs.

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
