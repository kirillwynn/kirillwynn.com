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
  rollout-state.json
```

This schema-2 document is the only authoritative activation point. It contains
exact `active.application`, production-owned `active.edge`, `previous`, the
in-progress operation ID, a recovery-required pointer, and every immutable-ID
attempt with phase history and evidence. Manifests are referenced by path and
SHA-256 and are never rewritten. Every transition writes and `fsync`s a
mode-0600 temporary file, atomically replaces the document, and `fsync`s its
directory.

The attempt is durable before any PostgreSQL/application/edge mutation.
Repeating the same operation and phase is a no-op; a reused operation ID with
different input, another in-progress operation, a stale sequence, or a second
operation for an already-active release is rejected. Finalize performs one
atomic A → B switch that preserves A as rollback target. Repeating finalize B
does not write state. Staging owns only application state because it does not
replace shared edge; production state records both application and exact live
edge digest.

Staging and production GitHub jobs share
`kirillwynn-server-release-operations`; the server also uses
`/srv/kirillwynn/locks/release.lock`. Staging records a monotonic GitHub run
sequence so an older completed `main` build cannot replace a newer active
release.

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

With no active snapshot in
`/srv/kirillwynn/state/production/rollout-state.json`:

1. validate the manifest and five runtime files;
2. install the versioned bundle/runtime files;
3. durably record the immutable operation ID;
4. prove the environment-qualified PostgreSQL volume does not exist, then
   persist the operation's volume-creation authorization;
5. use `infra/compose/database.yml` to pull and start only the pinned
   PostgreSQL digest with bounded `--wait`;
6. take an `initial-empty` custom-format backup and verify
   `pg_restore --list`; no Django, Next, worker, migration, or public service
   starts before this backup;
7. pull exact Django/Next digests;
8. run `migrate --noinput`; a retry after a lost response uses the durable
   `migration-started` phase and database migration plan rather than blindly
   repeating completed work;
9. start the application with bounded `--wait`;
10. verify Django readiness, Next health, worker heartbeat, worker provider
   egress, and exact active image references;
11. validate/replace edge, run public smoke, then atomically activate state.

This empty-initial-backup policy is the documented equivalent of "backup the
existing database" for the first production deployment. An existing volume
without an active snapshot or the same operation's saved
`bootstrap-volume-authorized` phase fails closed. Never delete it, adopt it, or
assume it is empty. Resume an interrupted first deploy with exactly the
original operation ID; a new operation cannot inherit its bootstrap phases.

Every subsequent deployment uses the active runtime contract to back up the
existing database before migration. The PostgreSQL digest cannot change in an
application rollout; database upgrades require separate review.

## Normal rollout and attestation

The enforced application order is durable attempt → purpose-typed backup →
pull exact app digests → one migration → `up --wait` → Django readiness → Next
health → worker heartbeat → worker outbound HTTP path → exact container image
references. These checks advance the same attempt to pending public smoke.

The CI caller then performs public health/readiness/root smoke (with staging
Basic Auth where applicable) and finalizes state. Staging attestation schema 3
contains the exact manifest images and affirmative evidence for public smoke,
Django/Next health, worker heartbeat, worker egress, exact active application
image digests, the immutable operation ID, and the exact edge candidate's
successful `nginx -t`. Production accepts only an exact matching attestation.
Immediately before the atomic switch, `finalize_rollout.sh` rechecks live
application health/digests and production edge digest/live `nginx -t`
(staging rechecks its edge candidate), so recorded active component state
cannot rely on a stale pre-smoke observation.

Production edge replacement occurs after the application health gates and
before public smoke. If public smoke fails, `mark_rollout_failed.sh` preserves
candidate and failure evidence, leaves the prior active/previous snapshots
unchanged, and requires explicit recovery. Do not start a new deployment or
use normal rollback while recovery is required.

## Reviewed abort and failed-smoke recovery

An attempt may be aborted only while its phase is still `attempt-recorded`,
before a volume, database, application, or edge mutation:

```bash
flock -w 900 /srv/kirillwynn/locks/release.lock \
  /srv/kirillwynn/releases/<candidate-sha>/infra/scripts/abort_rollout.sh \
  production <operation-id> "reviewed reason"
```

After any mutation, restore the failed operation's exact base snapshot. For
active=A, previous=Z, failed candidate=B, choose a new reviewed recovery
operation ID and a sequence greater than B:

```bash
flock -w 900 /srv/kirillwynn/locks/release.lock \
  /srv/kirillwynn/releases/<candidate-sha>/infra/scripts/recover_failed_rollout.sh \
  production <failed-operation-id-B> <recovery-operation-id> \
  <next-sequence> /srv/kirillwynn/runtime/edge.env
```

The script takes a `recovery` backup of the failed candidate database, restores
A's exact Django/worker/Next digests, restores and verifies production edge A,
checks readiness, Next health, heartbeat, egress, exact images, candidate and
live `nginx -t`, then leaves the recovery pending. Run public health,
readiness, and root smoke. On failure, mark the recovery operation failed and
retain all evidence. On success:

```bash
flock -w 900 /srv/kirillwynn/locks/release.lock \
  /srv/kirillwynn/releases/<candidate-sha>/infra/scripts/finalize_rollout.sh \
  production <recovery-operation-id>
```

Finalize is idempotent. It clears recovery ownership only after successful
public smoke, keeps B's failed evidence, keeps Z as the normal rollback target,
and records active application/edge exactly as A.

## Reproducible application rollback

Rollback is allowed only when the previous digest is compatible with the
current schema. It does not rebuild and does not trust Git:

```bash
flock -w 900 /srv/kirillwynn/locks/release.lock \
  /srv/kirillwynn/releases/<current-sha>/infra/scripts/rollback_environment.sh \
  production <rollback-operation-id> <next-sequence> \
  /srv/kirillwynn/runtime/edge.env
```

The script selects the authoritative previous component snapshot, proves its
immutable bundle/runtime exist, refuses a PostgreSQL image change, takes a
`recovery` backup, restores the previous Django/Next/worker and production edge
digests, and performs health/digest/Nginx gates without running or reversing
migrations. It leaves the operation pending. Run public smoke, then finalize:

```bash
flock -w 900 /srv/kirillwynn/locks/release.lock \
  /srv/kirillwynn/releases/<rollback-sha>/infra/scripts/finalize_rollout.sh \
  production <rollback-operation-id>
```

Production rollback always restores edge with the same target snapshot; it
cannot record application A active while edge B remains live. Staging rollback
does not replace shared edge and records only its application truth.
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
