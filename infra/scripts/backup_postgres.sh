#!/bin/sh
set -eu

usage() {
    echo "usage: backup_postgres.sh <staging|production> <env-file> <release-sha> [backup-dir]" >&2
    exit 2
}

[ "$#" -ge 3 ] && [ "$#" -le 4 ] || usage
environment_name=$1
env_file=$2
release_sha=$3
backup_root=${4:-/srv/kirillwynn/backups}
case "$environment_name" in
    staging|production) ;;
    *) usage ;;
esac
case "$release_sha" in
    *[!0-9a-f]*|"") echo "release SHA must be hexadecimal" >&2; exit 2 ;;
esac
[ "${#release_sha}" -eq 40 ] || { echo "release SHA must contain 40 characters" >&2; exit 2; }

repository_root=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
database=$(python3 "$repository_root/infra/scripts/env_value.py" "$env_file" POSTGRES_DB)
database_user=$(python3 "$repository_root/infra/scripts/env_value.py" "$env_file" POSTGRES_USER)
project_name="kirillwynn-$environment_name"
timestamp=$(date -u +%Y%m%dT%H%M%SZ)
backup_dir="$backup_root/$environment_name"
umask 077
mkdir -p "$backup_dir"
temporary=$(mktemp "$backup_dir/.${timestamp}.XXXXXX.dump")
trap 'rm -f "$temporary"' EXIT HUP INT TERM

docker compose \
    --project-name "$project_name" \
    --env-file "$env_file" \
    -f "$repository_root/infra/compose/application.yml" \
    exec -T postgres pg_dump \
    --username "$database_user" \
    --dbname "$database" \
    --format custom \
    --no-owner \
    --no-acl > "$temporary"

docker compose \
    --project-name "$project_name" \
    --env-file "$env_file" \
    -f "$repository_root/infra/compose/application.yml" \
    exec -T postgres pg_restore --list < "$temporary" > /dev/null

final_dump="$backup_dir/${timestamp}_${release_sha}.dump"
mv "$temporary" "$final_dump"
trap - EXIT HUP INT TERM
checksum=$(shasum -a 256 "$final_dump" | awk '{print $1}')
python3 - "$environment_name" "$release_sha" "$timestamp" "$checksum" "$final_dump" <<'PY'
import json
import os
import sys
import tempfile
from pathlib import Path

environment, release, timestamp, checksum, dump = sys.argv[1:]
target = Path(f"{dump}.json")
payload = {
    "schema_version": 1,
    "environment": environment,
    "release_sha": release,
    "created_at": timestamp,
    "sha256": checksum,
    "dump_file": Path(dump).name,
}
descriptor, temporary = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.")
with os.fdopen(descriptor, "w") as handle:
    json.dump(payload, handle, sort_keys=True)
    handle.write("\n")
    handle.flush()
    os.fsync(handle.fileno())
os.chmod(temporary, 0o600)
os.replace(temporary, target)
PY

echo "$final_dump"
