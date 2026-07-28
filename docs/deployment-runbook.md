# Deployment and rollback runbook

## Runtime contracts and minimum versions

The server requires Docker Compose 2.30.0 or newer. Run
`infra/scripts/require_compose_version.sh` before activation. The minimum is
required for `env_file.format: raw`; do not remove `raw` or quote secrets to
work around an older Compose.

One edge project owns ports 80/443 and both named edge networks. Staging and
production each own:

- an internal PostgreSQL-only database network;
- an internal application network for Django/Next/worker calls;
- an egress bridge with no published ports for Django/Next/worker outbound;
- a PostgreSQL volume and Next cache volume.

PostgreSQL joins only database. Next does not join database. Worker joins
database/application/egress but never edge. Django and Next alone receive
environment-qualified edge aliases.

Runtime files are role-scoped:

```text
/srv/kirillwynn/runtime/releases/<sha>/<environment>/
  control.env   # project, paths, networks, aliases, sequence, pinned images
  postgres.env  # DB, user, password
  django.env    # Django/S3/OAuth/webhook/session contract
  worker.env    # minimal Django/S3/Resend worker contract
  next.env      # PUBLIC_SITE_URL, DJANGO_API_URL, REVALIDATION_SECRET
```

Only `control.env` is passed as Compose interpolation input. The other files
are loaded by the intended container with raw semantics. Validators reject
extra, missing, multiline, NUL, oversized, or cross-environment values.

## Durable release and active state

CI copies a release-owned bundle from the checked-out SHA into:

```text
/srv/kirillwynn/releases/<sha>/
  release-manifest.json
  infra/compose/
  infra/scripts/
```

It never executes a server Git checkout. Runtime candidates and these bundles
survive cleanup of `/tmp/kirillwynn-deploy-*`.

Per-environment operational state is:

```text
/srv/kirillwynn/state/<environment>/
  active-release.json
  current-manifest.json
  previous-manifest.json
  pending-<sha>.json       # exists only between internal and public gates
```

The current/previous files change only after every internal gate and public
smoke succeeds. A failed rollout never marks the new manifest active. Pending
state blocks another rollout until the failure is resolved. Staging and
production GitHub jobs share `kirillwynn-server-release-operations`; the
server also uses `/srv/kirillwynn/locks/release.lock`. Staging records a
monotonic GitHub run sequence so an older completed `main` build cannot replace
a newer active release.

## Initial shared edge

Before the first application activation, install TLS/ACME/auth mounts, validate
the exact edge digest with `verify_edge_candidate.sh`, and start edge with
`deploy_edge.sh` under the server release lock. Edge creates both named edge
networks and starts even while staging and production aliases do not exist.
The absent host returns bounded 502; the other host remains independent.

Nginx 1.29 uses Docker DNS, resolver timeouts, shared upstream zones, and
`server ... resolve`. Replacing Django/Next is detected without edge restart.
Every edge replacement still runs the candidate `nginx -t` before `up`, then
`nginx -t` in the live container.

## First production deploy

With no `/srv/kirillwynn/state/production/active-release.json`:

1. validate the manifest and five runtime files;
2. install the versioned bundle/runtime files;
3. use `infra/compose/database.yml` to pull and start only the pinned
   PostgreSQL digest with bounded `--wait`;
4. take a custom-format backup of the initial database and verify
   `pg_restore --list`; no Django, Next, worker, migration, or public service
   starts before this backup;
5. pull exact Django/Next digests;
6. run `migrate --noinput` exactly once;
7. start the application with bounded `--wait`;
8. verify Django readiness, Next health, worker heartbeat, worker provider
   egress, and exact active image references;
9. validate/replace edge, run public smoke, then atomically activate state.

This empty-initial-backup policy is the documented equivalent of "backup the
existing database" for the first production deployment. If a PostgreSQL
volume exists without active state, stop and reconcile it; do not delete or
assume it is empty.

Every subsequent deployment uses the active runtime contract to back up the
existing database before migration. The PostgreSQL digest cannot change in an
application rollout; database upgrades require separate review.

## Normal rollout and attestation

The enforced application order is backup → pull exact app digests → one
migration → `up --wait` → Django readiness → Next health → worker heartbeat →
worker outbound HTTP path → exact container image references. These checks
create only pending state.

The CI caller then performs public health/readiness/root smoke (with staging
Basic Auth where applicable) and finalizes state. Staging attestation schema 2
contains the exact manifest images and affirmative evidence for public smoke,
Django/Next health, worker heartbeat, worker egress, exact active application
image digests, and the exact edge candidate's successful `nginx -t`.
Production accepts only an exact matching attestation.

Production edge replacement occurs after the application health gates and
before public smoke. If public smoke fails, the new application/edge may be
running but the manifest is not active; retain pending evidence and either fix
forward or perform the reviewed rollback below.

## Reproducible application rollback

Rollback is allowed only when the previous digest is compatible with the
current schema. It does not rebuild and does not trust Git:

```bash
flock -w 900 /srv/kirillwynn/locks/release.lock \
  /srv/kirillwynn/releases/<current-sha>/infra/scripts/rollback_environment.sh \
  staging
```

The script selects `previous-manifest.json`, proves its durable bundle/runtime
exist, refuses a PostgreSQL image change, backs up the active database, pulls
the previous Django/Next digests, and performs the health/digest gates without
running or reversing migrations. It leaves pending state. Run the public smoke,
then finalize with the selected durable bundle:

```bash
flock -w 900 /srv/kirillwynn/locks/release.lock \
  /srv/kirillwynn/releases/<rollback-sha>/infra/scripts/finalize_rollout.sh \
  staging <rollback-sha>
```

Do not roll edge back unless route compatibility requires it; if required,
run the previous bundle's `verify_edge_candidate.sh` before `deploy_edge.sh`.
A reverse migration always needs a new verified backup, scratch restore
rehearsal, and separate approval.

## Route contract

Next owns `/`, `/posts/*`, `/bridge`, account/subscription UI, `/_next/*`, and
exact `/api/draft`, `/api/draft/disable`, `/api/revalidate`. Django owns
health/readiness/session endpoints, `/api/v1/*`, `/accounts/*`, `/cms/*`, and
`/django-admin/*`. `/media/documents/*` redirects through Django/S3; other
`/media/*` and unknown `/api/*` return 404. Staging Basic Auth excludes only
ACME and the exact signed Resend webhook. Edge replaces, never appends, inbound
forwarding headers.
