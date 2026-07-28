#!/bin/sh
set -eu

[ "$#" -eq 5 ] || {
    echo "usage: recover_failed_rollout.sh <staging|production> <failed-operation-id> <recovery-operation-id> <deployment-sequence> <edge-runtime-env>" >&2
    exit 2
}
environment_name=$1
failed_operation_id=$2
operation_id=$3
deployment_sequence=$4
edge_runtime_env=$5
case "$environment_name" in
    staging|production) ;;
    *) exit 2 ;;
esac

repository_root=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
state_root=${STATE_DIRECTORY:-/srv/kirillwynn/state}
backup_root=${BACKUP_DIRECTORY:-/srv/kirillwynn/backups}
state_script="$repository_root/infra/scripts/record_rollout_state.py"

operation_field() {
    python3 "$state_script" inspect \
        --environment "$environment_name" \
        --operation-id "$1" \
        --field "$2" \
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

# This is an explicit reviewed operation. The failed attempt and its public
# smoke evidence remain in the authoritative document throughout recovery.
python3 "$state_script" begin-recovery \
    --environment "$environment_name" \
    --operation-id "$operation_id" \
    --failed-operation-id "$failed_operation_id" \
    --deployment-sequence "$deployment_sequence" \
    --state-directory "$state_root"

status=$(operation_field "$operation_id" status)
case "$status" in
    completed) exit 0 ;;
    failed)
        echo "failed recovery requires another reviewed recovery operation" >&2
        exit 2
        ;;
    in-progress) ;;
    *) echo "recovery operation is not resumable" >&2; exit 2 ;;
esac

failed_runtime=$(operation_field \
    "$failed_operation_id" candidate.application.runtime_directory)
failed_sha=$(operation_field "$failed_operation_id" candidate.application.release_sha)
recovery_runtime=$(operation_field \
    "$operation_id" candidate.application.runtime_directory)
recovery_manifest=$(operation_field \
    "$operation_id" candidate.application.manifest_path)
control_env="$recovery_runtime/control.env"
compose_file="$(dirname "$recovery_manifest")/infra/compose/application.yml"

test "$(python3 "$repository_root/infra/scripts/env_value.py" \
    "$failed_runtime/control.env" POSTGRES_IMAGE)" = \
    "$(python3 "$repository_root/infra/scripts/env_value.py" \
    "$control_env" POSTGRES_IMAGE)" || {
    echo "recovery cannot change the PostgreSQL image" >&2
    exit 2
}
"$repository_root/infra/scripts/bootstrap_database.sh" \
    "$environment_name" "$recovery_runtime" \
    "$(operation_field "$operation_id" candidate.application.release_sha)" \
    "$operation_id" "$backup_root"

if needs recovery-backup-started; then
    checkpoint recovery-backup-started
fi
if needs recovery-backup-completed; then
    "$repository_root/infra/scripts/backup_postgres.sh" \
        "$environment_name" "$failed_runtime" "$failed_sha" "$backup_root" \
        recovery "$operation_id"
    checkpoint recovery-backup-completed
fi

if needs application-rollout-started; then
    checkpoint application-rollout-started
fi
if needs application-healthy; then
    docker compose --env-file "$control_env" -f "$compose_file" \
        pull django next worker
    docker compose --env-file "$control_env" -f "$compose_file" up \
        -d --remove-orphans --wait \
        --wait-timeout "${ROLLOUT_WAIT_TIMEOUT_SECONDS:-180}"
    "$repository_root/infra/scripts/verify_application_rollout.sh" \
        "$recovery_runtime" "$recovery_manifest" "$compose_file"
    checkpoint application-healthy
fi

# Production deploy_edge performs candidate nginx -t before replacement,
# live nginx -t after replacement, and exact edge digest inspection. Staging
# does not own edge and only revalidates the candidate configuration.
"$repository_root/infra/scripts/advance_edge_rollout.sh" \
    "$environment_name" "$operation_id" "$recovery_manifest" "$edge_runtime_env"
echo "recovery is pending public smoke; failed evidence remains authoritative"
