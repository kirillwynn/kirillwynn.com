# PostgreSQL backup and restore

Database operations use `infra/compose/database.yml`, not the application
model. This contract contains only pinned PostgreSQL, the role-scoped
`postgres.env`, the environment-qualified database network, and the existing
PostgreSQL volume. The volume is external: Compose cannot create or delete it.
Before any Compose database use, rollout orchestration verifies the exact
environment, `postgres-data` role, immutable bootstrap-operation, and
volume-name labels against schema-3 `rollout-state.json`. It cannot require or
interpolate `DJANGO_IMAGE` or `NEXT_IMAGE`.

Use the runtime directory for the active release:

```bash
/srv/kirillwynn/releases/<sha>/infra/scripts/backup_postgres.sh \
  staging \
  /srv/kirillwynn/runtime/releases/<sha>/staging \
  <full-release-sha> \
  /srv/kirillwynn/backups \
  manual \
  <immutable-operation-id>
```

The script writes an environment-qualified custom-format dump, verifies
`pg_restore --list`, and creates a mode-0600 JSON sidecar containing schema
version, environment, UTC timestamp, release SHA, dump filename, SHA-256,
immutable operation ID, and one explicit purpose:

- `initial-empty` — the newly created first-deploy database before migration;
- `pre-migration` — every later rollout's active database;
- `recovery` — rollback, failed rollout recovery, retry, or fix-forward evidence;
- `manual` — a reviewed operator backup.

Both remain outside Git under `/srv/kirillwynn/backups/<environment>/`.

First production deployment starts only the pinned PostgreSQL service and takes
an `initial-empty` backup before its first migration. It refuses an existing
volume before authorization, explicitly creates the authorized volume with
ownership labels, and accepts an existing volume only when every ownership
label matches. `initial-empty` is recorded once in the authoritative database
lifecycle snapshot. A failed first deployment may leave `active=null`, but its
`ready` or `migrated` database remains owned and recoverable.

Every later ordinary deployment takes `pre-migration`; rollback and active-A
recovery take `recovery`. A reviewed same-candidate retry finishes the original
initial backup only when the database never crossed migration; otherwise it
takes `recovery`. Fix-forward to a new release always takes `recovery` before
migration and must never take `initial-empty` over an existing database.
Backup dumps and sidecars are immutable and never overwritten. No backup,
recovery, rollback, or deployment script removes the PostgreSQL volume.

Retention remains explicit:

```bash
/srv/kirillwynn/releases/<sha>/infra/scripts/prune_backups.sh staging 14 /srv/kirillwynn/backups
/srv/kirillwynn/releases/<sha>/infra/scripts/prune_backups.sh production 35 /srv/kirillwynn/backups
```

Restore refuses to run `createdb` until the required sidecar exists and its
shape, source environment, dump filename, and SHA-256 match. `pg_restore
--list` is the second pre-mutation gate. Restore creates only a new
`restore_*` database and fails if it already exists:

```bash
/srv/kirillwynn/releases/<sha>/infra/scripts/restore_postgres.sh \
  staging \
  /srv/kirillwynn/runtime/releases/<sha>/staging \
  /srv/kirillwynn/backups/staging/<backup>.dump \
  restore_drill_20260727
```

Production-source restore preserves typed confirmation:

```bash
/srv/kirillwynn/releases/<sha>/infra/scripts/restore_postgres.sh \
  production \
  /srv/kirillwynn/runtime/releases/<sha>/production \
  /srv/kirillwynn/backups/production/<backup>.dump \
  restore_incident_20260727 \
  "RESTORE production restore_incident_20260727"
```

Pointing an application at restored data, renaming databases, or deleting
scratch data is a separate approved incident action. Monthly staging drills
must restore the newest dump, run Django migration/check plans, compare key row
counts, and record duration/results.

## Staging stabilization audit drill

The manual `staging-stabilization-audit.yml` workflow is the bounded repository
implementation of a fresh staging recovery drill. Dispatch it only with the
exact application release currently recorded as active in schema-3 rollout
state. The entire workflow holds `kirillwynn-server-release-operations`, so a
deployment, recovery, or catalog operation cannot interleave between its
server snapshot and live browser acceptance.

The workflow verifies the active application and separately retained shared
Edge references, committed/active Compose and runtime contracts, container
health, and absence of production application state, containers, volumes, and
private networks. ADR 0005 requires the shared Edge project to own the dormant
production edge network even before production exists; the audit therefore
requires that exact network to contain only the active shared Edge container.
It reads the active database inside PostgreSQL read-only transactions, creates
a purpose `manual`
custom-format backup, verifies schema-2 metadata/SHA-256 and
`pg_restore --list`, and restores only into a new
`restore_stage18_<run>_<attempt>` database. The scratch database is never
attached to the public application and is intentionally retained for reviewed
operator cleanup. The workflow does not replace the active database and does
not delete a database or volume.

Migration plans, Django checks, PII-free integrity counts/invariants, and
three-sample query-count/server-time baselines run against the restore. A second
read-only active snapshot distinguishes concurrent user activity from backup
drift, while identity, migration, ownerless-post, SocialToken, and reaction
catalog invariants remain strict. Release state must be byte-equivalent before
and after the drill. All retrieved recovery and five-viewport Playwright
evidence passes the repository artifact sanitizer before upload. The workflow
has no deployment, reaction-catalog sync, or production path.

PostgreSQL dumps do not contain media. S3 buckets remain environment-specific
and require provider versioning/lifecycle/off-site protection plus a staging
recovery drill for an original, rendition, and document.
