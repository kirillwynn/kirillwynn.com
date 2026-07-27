# PostgreSQL backup and restore

`infra/scripts/backup_postgres.sh` runs environment-qualified custom-format
`pg_dump`, validates with `pg_restore --list`, then atomically accepts the dump
and metadata with UTC timestamp, release SHA, and checksum.

```bash
infra/scripts/backup_postgres.sh \
  staging /srv/kirillwynn/runtime/staging.env <full-release-sha>
```

Production promotion uses the production equivalent as a mandatory gate.
Backups live outside Git under `/srv/kirillwynn/backups/<environment>/`.
Retention is explicit:

```bash
infra/scripts/prune_backups.sh staging 14 /srv/kirillwynn/backups
infra/scripts/prune_backups.sh production 35 /srv/kirillwynn/backups
```

Restore always creates a new `restore_*` scratch database and fails if it
exists:

```bash
infra/scripts/restore_postgres.sh \
  staging /srv/kirillwynn/runtime/staging.env <backup.dump>
```

Production-source restore additionally requires the exact confirmation:

```bash
infra/scripts/restore_postgres.sh \
  production /srv/kirillwynn/runtime/production.env <backup.dump> \
  restore_incident_20260727 \
  "RESTORE production restore_incident_20260727"
```

This still targets only the new scratch database. Pointing an app at restored
data, renaming, or deleting databases is a separate approved incident action.

Monthly staging drill: restore the newest dump to scratch; run Django
`migrate --plan` and `check`; compare key row counts; open representative
Wagtail pages through a temporary protected task; record duration/result.
Scratch deletion is separately reviewed.

Media is not in PostgreSQL dumps. Configure S3 versioning, lifecycle, and
off-site replication where available, then test recovery of an original,
rendition, and document in staging. Never share a production bucket/prefix or
credential with staging.
