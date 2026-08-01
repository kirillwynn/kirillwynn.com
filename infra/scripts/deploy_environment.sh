#!/bin/sh
set -eu

usage() {
    echo "usage: deploy_environment.sh <staging|production> <runtime-dir> <release-manifest> <operation-id> [retry|fix-forward <failed-operation-id> <deployment-sequence>]" >&2
    exit 2
}

[ "$#" -eq 4 ] || [ "$#" -eq 7 ] || usage
environment_name=$1
runtime_dir=$2
release_manifest=$3
operation_id=$4
resolution_kind=${5:-}
failed_operation_id=${6:-}
resolution_deploy_sequence=${7:-}
case "$environment_name" in
    staging|production) ;;
    *) usage ;;
esac

repository_root=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
control_env="$runtime_dir/control.env"
compose_file="$repository_root/infra/compose/application.yml"
state_root=${STATE_DIRECTORY:-/srv/kirillwynn/state}
backup_root=${BACKUP_DIRECTORY:-/srv/kirillwynn/backups}
state_script="$repository_root/infra/scripts/record_rollout_state.py"
migration_worker_paused=false

restore_migration_worker() {
    if [ "$migration_worker_paused" = true ]; then
        # The existing worker container belongs to the still-active release.
        # Starting, rather than recreating, it keeps a failed pre-migration
        # attempt on the previous digest and restores durable outbox delivery.
        docker compose --env-file "$control_env" -f "$compose_file" \
            start worker >/dev/null 2>&1 || true
        migration_worker_paused=false
    fi
}

trap restore_migration_worker EXIT HUP INT TERM

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

operation_field() {
    python3 "$state_script" inspect \
        --environment "$environment_name" \
        --operation-id "$operation_id" \
        --field "$1" \
        --state-directory "$state_root"
}

"$repository_root/infra/scripts/require_compose_version.sh"
python3 "$repository_root/infra/scripts/validate_release_manifest.py" "$release_manifest"
release_sha=$(python3 "$repository_root/infra/scripts/env_value.py" \
    "$control_env" RELEASE_SHA)
if [ -n "$resolution_kind" ]; then
    deploy_sequence=$resolution_deploy_sequence
else
    deploy_sequence=$(python3 "$repository_root/infra/scripts/env_value.py" \
        "$control_env" DEPLOY_SEQUENCE)
fi
postgres_volume=$(python3 "$repository_root/infra/scripts/env_value.py" \
    "$control_env" POSTGRES_VOLUME)
postgres_image=$(python3 "$repository_root/infra/scripts/env_value.py" \
    "$control_env" POSTGRES_IMAGE)
python3 "$repository_root/infra/scripts/validate_release_manifest.py" \
    "$release_manifest" --expect-sha "$release_sha"

django_image=$(python3 "$repository_root/infra/scripts/release_image.py" \
    "$release_manifest" django)
next_image=$(python3 "$repository_root/infra/scripts/release_image.py" \
    "$release_manifest" next)
test "$django_image" = "$(python3 "$repository_root/infra/scripts/env_value.py" \
    "$control_env" DJANGO_IMAGE)" || {
    echo "control Django image does not match release manifest" >&2
    exit 2
}
test "$next_image" = "$(python3 "$repository_root/infra/scripts/env_value.py" \
    "$control_env" NEXT_IMAGE)" || {
    echo "control Next image does not match release manifest" >&2
    exit 2
}

umask 077
mkdir -p "$backup_root"
# The durable attempt is the first state mutation and precedes any Docker,
# PostgreSQL, application, or edge mutation. Reusing the same immutable
# operation ID resumes; a different operation cannot adopt its progress.
if [ -n "$resolution_kind" ]; then
    case "$resolution_kind" in
        retry|fix-forward) ;;
        *) usage ;;
    esac
    python3 "$state_script" begin-resolution \
        --environment "$environment_name" \
        --operation-id "$operation_id" \
        --failed-operation-id "$failed_operation_id" \
        --resolution "$resolution_kind" \
        --release-sha "$release_sha" \
        --deployment-sequence "$deploy_sequence" \
        --runtime-directory "$runtime_dir" \
        --manifest "$release_manifest" \
        --postgres-volume "$postgres_volume" \
        --postgres-image "$postgres_image" \
        --state-directory "$state_root"
else
    python3 "$state_script" begin \
        --environment "$environment_name" \
        --operation-id "$operation_id" \
        --operation deploy \
        --release-sha "$release_sha" \
        --deployment-sequence "$deploy_sequence" \
        --runtime-directory "$runtime_dir" \
        --manifest "$release_manifest" \
        --postgres-volume "$postgres_volume" \
        --postgres-image "$postgres_image" \
        --state-directory "$state_root"
fi

operation_status=$(operation_field status)
case "$operation_status" in
    completed) exit 0 ;;
    failed)
        echo "failed rollout requires an explicit reviewed recovery operation" >&2
        exit 2
        ;;
    in-progress) ;;
    *) echo "rollout operation is not resumable" >&2; exit 2 ;;
esac
operation_plan=$(python3 "$state_script" plan \
    --environment "$environment_name" \
    --operation-id "$operation_id" \
    --state-directory "$state_root")

"$repository_root/infra/scripts/bootstrap_database.sh" \
    "$environment_name" "$runtime_dir" "$release_sha" "$operation_id" \
    "$backup_root"

if needs_optional pre-migration-backup-started; then
    checkpoint pre-migration-backup-started
fi
if needs_optional pre-migration-backup-completed; then
    active_runtime=$(operation_field base_active.application.runtime_directory)
    active_sha=$(operation_field base_active.application.release_sha)
    active_postgres_image=$(python3 "$repository_root/infra/scripts/env_value.py" \
        "$active_runtime/control.env" POSTGRES_IMAGE)
    incoming_postgres_image=$(python3 "$repository_root/infra/scripts/env_value.py" \
        "$control_env" POSTGRES_IMAGE)
    test "$active_postgres_image" = "$incoming_postgres_image" || {
        echo "PostgreSQL image changes require a reviewed database upgrade" >&2
        exit 2
    }
    "$repository_root/infra/scripts/backup_postgres.sh" \
        "$environment_name" "$active_runtime" "$active_sha" "$backup_root" \
        pre-migration "$operation_id"
    checkpoint pre-migration-backup-completed
fi
if needs_optional recovery-backup-started; then
    checkpoint recovery-backup-started
fi
if needs_optional recovery-backup-completed; then
    failed_runtime=$(operation_field base_database.bootstrap_runtime_directory)
    failed_sha=$(operation_field candidate.application.release_sha)
    if [ -n "$failed_operation_id" ]; then
        failed_runtime=$(python3 "$state_script" inspect \
            --environment "$environment_name" \
            --operation-id "$failed_operation_id" \
            --field candidate.application.runtime_directory \
            --state-directory "$state_root")
        failed_sha=$(python3 "$state_script" inspect \
            --environment "$environment_name" \
            --operation-id "$failed_operation_id" \
            --field candidate.application.release_sha \
            --state-directory "$state_root")
    fi
    "$repository_root/infra/scripts/backup_postgres.sh" \
        "$environment_name" "$failed_runtime" "$failed_sha" "$backup_root" \
        recovery "$operation_id"
    checkpoint recovery-backup-completed
fi

docker compose --env-file "$control_env" -f "$compose_file" pull django next worker

migration_started_now=false
if needs_optional migration-started; then
    checkpoint migration-started
    migration_started_now=true
fi
if needs_optional migration-completed; then
    worker_container=$(docker compose --env-file "$control_env" -f "$compose_file" \
        ps -q worker)
    if [ -n "$worker_container" ] && \
        [ "$(docker inspect --format '{{.State.Running}}' "$worker_container")" = true ]; then
        # A migration imports the same Django/Wagtail application as the
        # worker. Temporarily release that duplicate memory footprint on
        # small hosts. The web and Next containers remain live, and the EXIT
        # trap restores this exact worker container if any later gate fails.
        docker compose --env-file "$control_env" -f "$compose_file" \
            stop --timeout 60 worker
        migration_worker_paused=true
    fi
    if [ "$migration_started_now" = true ]; then
        docker compose --env-file "$control_env" -f "$compose_file" \
            run --rm --no-deps django python manage.py migrate --noinput
    else
        # A lost SSH response after migrate is resolved from database truth:
        # completed migrations are not invoked again; a partial idempotent
        # Django migration plan is resumed.
        migration_plan=$(docker compose --env-file "$control_env" \
            -f "$compose_file" run --rm --no-deps django \
            python manage.py migrate --plan)
        if printf '%s\n' "$migration_plan" | grep -q '\[ \]'; then
            docker compose --env-file "$control_env" -f "$compose_file" \
                run --rm --no-deps django python manage.py migrate --noinput
        fi
    fi
    checkpoint migration-completed
fi

if needs_optional application-rollout-started; then
    checkpoint application-rollout-started
fi
if needs_optional application-healthy; then
    docker compose --env-file "$control_env" -f "$compose_file" up \
        -d --remove-orphans --wait \
        --wait-timeout "${ROLLOUT_WAIT_TIMEOUT_SECONDS:-180}"
    "$repository_root/infra/scripts/verify_application_rollout.sh" \
        "$runtime_dir" "$release_manifest" "$compose_file"
    checkpoint application-healthy
    migration_worker_paused=false
fi

restore_migration_worker
trap - EXIT HUP INT TERM
