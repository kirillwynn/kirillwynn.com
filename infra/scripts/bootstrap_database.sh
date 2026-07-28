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
postgres_image=$(python3 "$repository_root/infra/scripts/env_value.py" \
    "$control_env" POSTGRES_IMAGE)

needs_optional() {
    printf '%s\n' "$operation_plan" | grep -Fxq -- "$1" || return 1
    checkpoint_status=$(python3 "$state_script" checkpoint-status \
        --environment "$environment_name" \
        --operation-id "$operation_id" \
        --phase "$1" \
        --state-directory "$state_root") || exit 2
    [ "$checkpoint_status" = needed ]
}

checkpoint() {
    python3 "$state_script" checkpoint \
        --environment "$environment_name" \
        --operation-id "$operation_id" \
        --phase "$1" \
        --state-directory "$state_root"
}

state_field() {
    python3 "$state_script" inspect \
        --environment "$environment_name" \
        --field "$1" \
        --state-directory "$state_root"
}

fault() {
    if [ "${BOOTSTRAP_DATABASE_FAULT:-}" = "$1" ]; then
        echo "injected bootstrap fault: $1" >&2
        exit 97
    fi
}

volume_exists() {
    docker volume inspect "$postgres_volume" >/dev/null 2>&1
}

verify_owned_volume() {
    actual_environment=$(docker volume inspect --format \
        '{{ index .Labels "com.kirillwynn.environment" }}' "$postgres_volume")
    actual_role=$(docker volume inspect --format \
        '{{ index .Labels "com.kirillwynn.role" }}' "$postgres_volume")
    actual_operation=$(docker volume inspect --format \
        '{{ index .Labels "com.kirillwynn.bootstrap-operation-id" }}' \
        "$postgres_volume")
    actual_identity=$(docker volume inspect --format \
        '{{ index .Labels "com.kirillwynn.volume-name" }}' "$postgres_volume")
    if [ "$actual_environment" != "$environment_name" ] ||
        [ "$actual_role" != postgres-data ] ||
        [ "$actual_operation" != "$bootstrap_operation_id" ] ||
        [ "$actual_identity" != "$postgres_volume" ]; then
        echo "PostgreSQL volume ownership labels do not match durable state" >&2
        exit 2
    fi
}

"$repository_root/infra/scripts/require_compose_version.sh"
operation_plan=$(python3 "$state_script" plan \
    --environment "$environment_name" \
    --operation-id "$operation_id" \
    --state-directory "$state_root")

if needs_optional bootstrap-volume-authorized; then
    if volume_exists; then
        echo "existing PostgreSQL volume has no durable bootstrap/rollout state" >&2
        exit 2
    fi
    checkpoint bootstrap-volume-authorized
    fault after-volume-authorization
fi

database_state=$(state_field database.lifecycle_state)
if [ "$database_state" = absent ]; then
    echo "database volume creation has no durable authorization" >&2
    exit 2
fi
test "$postgres_volume" = "$(state_field database.volume_name)" || {
    echo "runtime PostgreSQL volume conflicts with durable database identity" >&2
    exit 2
}
test "$postgres_image" = "$(state_field database.postgres_image)" || {
    echo "runtime PostgreSQL image conflicts with durable database identity" >&2
    exit 2
}
bootstrap_operation_id=$(state_field database.bootstrap_operation_id)

if [ "$database_state" = authorized ]; then
    if ! volume_exists; then
        docker volume create \
            --label "com.kirillwynn.environment=$environment_name" \
            --label "com.kirillwynn.role=postgres-data" \
            --label "com.kirillwynn.bootstrap-operation-id=$bootstrap_operation_id" \
            --label "com.kirillwynn.volume-name=$postgres_volume" \
            "$postgres_volume" >/dev/null
        fault after-volume-create
    fi
    verify_owned_volume
    docker compose \
        --env-file "$control_env" \
        -f "$database_compose" \
        pull postgres
    docker compose \
        --env-file "$control_env" \
        -f "$database_compose" \
        up -d --wait --wait-timeout "${ROLLOUT_WAIT_TIMEOUT_SECONDS:-180}" postgres
    fault after-container-start
    if needs_optional bootstrap-database-ready; then
        checkpoint bootstrap-database-ready
    fi
elif [ "$database_state" = ready ] || [ "$database_state" = migrated ]; then
    if ! volume_exists; then
        echo "confirmed database-ready PostgreSQL volume disappeared" >&2
        exit 2
    fi
    verify_owned_volume
else
    echo "unsupported durable database lifecycle state" >&2
    exit 2
fi

if needs_optional initial-backup-started; then
    checkpoint initial-backup-started
fi
if needs_optional initial-backup-completed; then
    "$repository_root/infra/scripts/backup_postgres.sh" \
        "$environment_name" "$runtime_dir" "$release_sha" "$backup_root" \
        initial-empty "$operation_id"
    checkpoint initial-backup-completed
fi
