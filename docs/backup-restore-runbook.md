# PostgreSQL backup and restore

Database operations use `infra/compose/database.yml`, not the application
model. This contract contains only pinned PostgreSQL, the role-scoped
`postgres.env`, the environment-qualified database network, and the existing
PostgreSQL volume. It cannot require or interpolate `DJANGO_IMAGE` or
`NEXT_IMAGE`.

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
- `recovery` — rollback or failed-smoke recovery evidence;
- `manual` — a reviewed operator backup.

Both remain outside Git under `/srv/kirillwynn/backups/<environment>/`.

First production deployment starts only the pinned PostgreSQL service and takes
an `initial-empty` backup before its first migration. It refuses an existing
volume unless the same durable bootstrap attempt already authorized its
creation. Every later deployment takes `pre-migration`; rollback/recovery takes
`recovery`. Backup dumps and sidecars are immutable and never overwritten.

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

PostgreSQL dumps do not contain media. S3 buckets remain environment-specific
and require provider versioning/lifecycle/off-site protection plus a staging
recovery drill for an original, rendition, and document.
