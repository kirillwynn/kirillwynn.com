#!/bin/sh
set -eu

[ "$#" -ge 3 ] && [ "$#" -le 4 ] || {
    echo "usage: bootstrap_database.sh <staging|production> <runtime-dir> <release-sha> [backup-dir]" >&2
    exit 2
}
environment_name=$1
runtime_dir=$2
release_sha=$3
backup_root=${4:-${BACKUP_DIRECTORY:-/srv/kirillwynn/backups}}
repository_root=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
control_env="$runtime_dir/control.env"

"$repository_root/infra/scripts/require_compose_version.sh"
docker compose \
    --env-file "$control_env" \
    -f "$repository_root/infra/compose/database.yml" \
    pull postgres
docker compose \
    --env-file "$control_env" \
    -f "$repository_root/infra/compose/database.yml" \
    up -d --wait --wait-timeout "${ROLLOUT_WAIT_TIMEOUT_SECONDS:-180}" postgres
"$repository_root/infra/scripts/backup_postgres.sh" \
    "$environment_name" "$runtime_dir" "$release_sha" "$backup_root"
