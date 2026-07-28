#!/bin/sh
set -eu

[ "$#" -ge 4 ] && [ "$#" -le 5 ] || {
    echo "usage: bootstrap_database.sh <staging|production> <runtime-dir> <release-sha> <operation-id> [backup-dir]" >&2
    exit 2
}
environment_name=$1
runtime_dir=$2
release_sha=$3
operation_id=$4
backup_root=${5:-${BACKUP_DIRECTORY:-/srv/kirillwynn/backups}}
repository_root=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
control_env="$runtime_dir/control.env"
state_root=${STATE_DIRECTORY:-/srv/kirillwynn/state}
state_script="$repository_root/infra/scripts/record_rollout_state.py"
database_compose="$repository_root/infra/compose/database.yml"
postgres_volume=$(python3 "$repository_root/infra/scripts/env_value.py" \
    "$control_env" POSTGRES_VOLUME)

needs() {
    python3 "$state_script" needs \
        --environment "$environment_name" \
        --operation-id "$operation_id" \
        --phase "$1" \
        --state-directory "$state_root"
}

checkpoint() {
    python3 "$state_script" checkpoint \
        --environment "$environment_name" \
        --operation-id "$operation_id" \
        --phase "$1" \
        --state-directory "$state_root"
}

"$repository_root/infra/scripts/require_compose_version.sh"

if needs bootstrap-volume-authorized; then
    if docker volume inspect "$postgres_volume" >/dev/null 2>&1; then
        echo "existing PostgreSQL volume has no durable bootstrap/rollout state" >&2
        exit 2
    fi
    # This checkpoint authorizes exactly this immutable attempt to create the
    # volume. A retry may continue only through the same operation ID.
    checkpoint bootstrap-volume-authorized
elif ! docker volume inspect "$postgres_volume" >/dev/null 2>&1; then
    echo "authorized bootstrap volume disappeared; refusing automatic recreation" >&2
    exit 2
fi

if needs bootstrap-database-ready; then
    docker compose \
        --env-file "$control_env" \
        -f "$database_compose" \
        pull postgres
    docker compose \
        --env-file "$control_env" \
        -f "$database_compose" \
        up -d --wait --wait-timeout "${ROLLOUT_WAIT_TIMEOUT_SECONDS:-180}" postgres
    checkpoint bootstrap-database-ready
fi

if needs initial-backup-completed; then
    "$repository_root/infra/scripts/backup_postgres.sh" \
        "$environment_name" "$runtime_dir" "$release_sha" "$backup_root" \
        initial-empty "$operation_id"
    checkpoint initial-backup-completed
fi
