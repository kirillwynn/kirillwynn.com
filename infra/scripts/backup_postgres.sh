#!/bin/sh
set -eu

usage() {
    echo "usage: backup_postgres.sh <staging|production> <runtime-dir> <release-sha> [backup-dir] [initial-empty|pre-migration|recovery|manual] [operation-id]" >&2
    exit 2
}

[ "$#" -ge 3 ] && [ "$#" -le 6 ] || usage
environment_name=$1
runtime_dir=$2
release_sha=$3
backup_root=${4:-${BACKUP_DIRECTORY:-/srv/kirillwynn/backups}}
backup_kind=${5:-manual}
operation_id=${6:-manual-$(date -u +%Y%m%dT%H%M%SZ)}
case "$environment_name" in
    staging|production) ;;
    *) usage ;;
esac
case "$release_sha" in
    *[!0-9a-f]*|"") echo "release SHA must be hexadecimal" >&2; exit 2 ;;
esac
[ "${#release_sha}" -eq 40 ] || {
    echo "release SHA must contain 40 characters" >&2
    exit 2
}
case "$backup_kind" in
    initial-empty|pre-migration|recovery|manual) ;;
    *) echo "unsupported backup kind" >&2; exit 2 ;;
esac
case "$operation_id" in
    *[!A-Za-z0-9._:-]*|"") echo "backup operation ID is invalid" >&2; exit 2 ;;
esac
[ "${#operation_id}" -ge 8 ] && [ "${#operation_id}" -le 128 ] || {
    echo "backup operation ID must contain 8-128 characters" >&2
    exit 2
}

repository_root=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
control_env="$runtime_dir/control.env"
postgres_env="$runtime_dir/postgres.env"
test -r "$control_env" && test -r "$postgres_env" || {
    echo "database runtime contract is incomplete" >&2
    exit 2
}
"$repository_root/infra/scripts/require_compose_version.sh"
database=$(python3 "$repository_root/infra/scripts/env_value.py" "$postgres_env" POSTGRES_DB)
database_user=$(python3 "$repository_root/infra/scripts/env_value.py" "$postgres_env" POSTGRES_USER)

timestamp=$(date -u +%Y%m%dT%H%M%SZ)
backup_dir="$backup_root/$environment_name"
umask 077
mkdir -p "$backup_dir"
temporary=$(mktemp "$backup_dir/.${timestamp}.XXXXXX.dump")
temporary_metadata="${temporary}.json"
trap 'rm -f "$temporary" "$temporary_metadata"' EXIT HUP INT TERM

set +e
docker compose \
    --env-file "$control_env" \
    -f "$repository_root/infra/compose/database.yml" \
    exec -T postgres pg_dump \
    --username "$database_user" \
    --dbname "$database" \
    --format custom \
    --no-owner \
    --no-acl > "$temporary"
dump_status=$?
set -e
[ "$dump_status" -eq 0 ] || {
    echo "PostgreSQL custom-format dump failed with status $dump_status" >&2
    exit 2
}
test -s "$temporary" || {
    echo "PostgreSQL custom-format dump is empty" >&2
    exit 2
}

set +e
docker compose \
    --env-file "$control_env" \
    -f "$repository_root/infra/compose/database.yml" \
    exec -T postgres pg_restore --list < "$temporary" > /dev/null
restore_list_status=$?
set -e
[ "$restore_list_status" -eq 0 ] || {
    echo "PostgreSQL dump listing failed with status $restore_list_status" >&2
    exit 2
}

checksum=$(shasum -a 256 "$temporary" | awk '{print $1}')
final_dump="$backup_dir/${timestamp}_${release_sha}_${backup_kind}_${operation_id}.dump"
test ! -e "$final_dump" && test ! -e "${final_dump}.json" || {
    echo "refusing to overwrite an immutable backup" >&2
    exit 2
}
python3 - "$environment_name" "$release_sha" "$timestamp" "$checksum" \
    "$final_dump" "$temporary_metadata" "$backup_kind" "$operation_id" <<'PY'
import json
import os
import sys
from pathlib import Path

environment, release, timestamp, checksum, dump, target, kind, operation_id = sys.argv[1:]
with open(target, "w") as handle:
    json.dump(
        {
            "schema_version": 2,
            "environment": environment,
            "release_sha": release,
            "created_at": timestamp,
            "sha256": checksum,
            "dump_file": Path(dump).name,
            "backup_kind": kind,
            "operation_id": operation_id,
        },
        handle,
        sort_keys=True,
    )
    handle.write("\n")
    handle.flush()
    os.fsync(handle.fileno())
os.chmod(target, 0o600)
PY
mv "$temporary" "$final_dump"
mv "$temporary_metadata" "${final_dump}.json"
python3 - "$final_dump" "${final_dump}.json" <<'PY'
import os
import sys
from pathlib import Path

for filename in sys.argv[1:]:
    descriptor = os.open(filename, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
backup_directory = Path(sys.argv[1]).parent
for directory in (backup_directory, backup_directory.parent):
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
PY
trap - EXIT HUP INT TERM
echo "$final_dump"
