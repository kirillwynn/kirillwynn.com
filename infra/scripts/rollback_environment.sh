#!/bin/sh
set -eu

[ "$#" -eq 4 ] || {
    echo "usage: rollback_environment.sh <staging|production> <operation-id> <deployment-sequence> <edge-runtime-env>" >&2
    exit 2
}
environment_name=$1
operation_id=$2
deployment_sequence=$3
edge_runtime_env=$4
case "$environment_name" in
    staging|production) ;;
    *) exit 2 ;;
esac

repository_root=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
state_root=${STATE_DIRECTORY:-/srv/kirillwynn/state}
backup_root=${BACKUP_DIRECTORY:-/srv/kirillwynn/backups}
state_script="$repository_root/infra/scripts/record_rollout_state.py"

state_field() {
    python3 "$state_script" inspect \
        --environment "$environment_name" \
        --field "$1" \
        --state-directory "$state_root"
}

operation_field() {
    python3 "$state_script" inspect \
        --environment "$environment_name" \
        --operation-id "$operation_id" \
        --field "$1" \
        --state-directory "$state_root"
}

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

if python3 "$state_script" inspect \
    --environment "$environment_name" \
    --operation-id "$operation_id" \
    --state-directory "$state_root" >/dev/null 2>&1; then
    rollback_manifest=$(operation_field candidate.application.manifest_path)
    rollback_runtime=$(operation_field candidate.application.runtime_directory)
    rollback_sha=$(operation_field candidate.application.release_sha)
else
    rollback_manifest=$(state_field previous.application.manifest_path)
    rollback_runtime=$(state_field previous.application.runtime_directory)
    rollback_sha=$(state_field previous.application.release_sha)
fi
control_env="$rollback_runtime/control.env"
postgres_volume=$(python3 "$repository_root/infra/scripts/env_value.py" \
    "$control_env" POSTGRES_VOLUME)
postgres_image=$(python3 "$repository_root/infra/scripts/env_value.py" \
    "$control_env" POSTGRES_IMAGE)

# The rollback attempt is durable before backup, application, or edge mutation.
python3 "$state_script" begin \
    --environment "$environment_name" \
    --operation-id "$operation_id" \
    --operation rollback \
    --release-sha "$rollback_sha" \
    --deployment-sequence "$deployment_sequence" \
    --runtime-directory "$rollback_runtime" \
    --manifest "$rollback_manifest" \
    --postgres-volume "$postgres_volume" \
    --postgres-image "$postgres_image" \
    --state-directory "$state_root"

status=$(operation_field status)
case "$status" in
    completed) exit 0 ;;
    failed)
        echo "failed rollback requires a reviewed recovery operation" >&2
        exit 2
        ;;
    in-progress) ;;
    *) echo "rollback operation is not resumable" >&2; exit 2 ;;
esac

current_runtime=$(operation_field base_active.application.runtime_directory)
current_sha=$(operation_field base_active.application.release_sha)
compose_file="$(dirname "$rollback_manifest")/infra/compose/application.yml"
test "$(python3 "$repository_root/infra/scripts/env_value.py" \
    "$current_runtime/control.env" POSTGRES_IMAGE)" = \
    "$(python3 "$repository_root/infra/scripts/env_value.py" \
    "$control_env" POSTGRES_IMAGE)" || {
    echo "rollback cannot change the PostgreSQL image" >&2
    exit 2
}
"$repository_root/infra/scripts/bootstrap_database.sh" \
    "$environment_name" "$rollback_runtime" "$rollback_sha" \
    "$operation_id" "$backup_root"

if needs recovery-backup-started; then
    checkpoint recovery-backup-started
fi
if needs recovery-backup-completed; then
    "$repository_root/infra/scripts/backup_postgres.sh" \
        "$environment_name" "$current_runtime" "$current_sha" "$backup_root" \
        recovery "$operation_id"
    checkpoint recovery-backup-completed
fi

if needs application-rollout-started; then
    checkpoint application-rollout-started
fi
if needs application-healthy; then
    docker compose --env-file "$control_env" -f "$compose_file" \
        pull django next worker
    # Rollback deliberately does not invoke migrate or reverse schema state.
    docker compose --env-file "$control_env" -f "$compose_file" up \
        -d --remove-orphans --wait \
        --wait-timeout "${ROLLOUT_WAIT_TIMEOUT_SECONDS:-180}"
    "$repository_root/infra/scripts/verify_application_rollout.sh" \
        "$rollback_runtime" "$rollback_manifest" "$compose_file"
    checkpoint application-healthy
fi

"$repository_root/infra/scripts/advance_edge_rollout.sh" \
    "$environment_name" "$operation_id" "$rollback_manifest" "$edge_runtime_env"
echo "rollback is pending public smoke; finalize only after external verification"
