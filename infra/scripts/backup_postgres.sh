#!/bin/sh
set -eu

usage() {
    echo "usage: backup_postgres.sh <staging|production> <runtime-dir> <release-sha> [backup-dir]" >&2
    exit 2
}

[ "$#" -ge 3 ] && [ "$#" -le 4 ] || usage
environment_name=$1
runtime_dir=$2
release_sha=$3
backup_root=${4:-${BACKUP_DIRECTORY:-/srv/kirillwynn/backups}}
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

docker compose \
    --env-file "$control_env" \
    -f "$repository_root/infra/compose/database.yml" \
    exec -T postgres pg_dump \
    --username "$database_user" \
    --dbname "$database" \
    --format custom \
    --no-owner \
    --no-acl > "$temporary"

docker compose \
    --env-file "$control_env" \
    -f "$repository_root/infra/compose/database.yml" \
    exec -T postgres pg_restore --list < "$temporary" > /dev/null

checksum=$(shasum -a 256 "$temporary" | awk '{print $1}')
final_dump="$backup_dir/${timestamp}_${release_sha}.dump"
python3 - "$environment_name" "$release_sha" "$timestamp" "$checksum" "$final_dump" "$temporary_metadata" <<'PY'
import json
import os
import sys
from pathlib import Path

environment, release, timestamp, checksum, dump, target = sys.argv[1:]
with open(target, "w") as handle:
    json.dump(
        {
            "schema_version": 1,
            "environment": environment,
            "release_sha": release,
            "created_at": timestamp,
            "sha256": checksum,
            "dump_file": Path(dump).name,
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
trap - EXIT HUP INT TERM
echo "$final_dump"
