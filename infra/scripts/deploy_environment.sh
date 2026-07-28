#!/bin/sh
set -eu

usage() {
    echo "usage: deploy_environment.sh <staging|production> <runtime-dir> <release-manifest> <operation-id>" >&2
    exit 2
}

[ "$#" -eq 4 ] || usage
environment_name=$1
runtime_dir=$2
release_manifest=$3
operation_id=$4
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
deploy_sequence=$(python3 "$repository_root/infra/scripts/env_value.py" \
    "$control_env" DEPLOY_SEQUENCE)
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
python3 "$state_script" begin \
    --environment "$environment_name" \
    --operation-id "$operation_id" \
    --operation deploy \
    --release-sha "$release_sha" \
    --deployment-sequence "$deploy_sequence" \
    --runtime-directory "$runtime_dir" \
    --manifest "$release_manifest" \
    --state-directory "$state_root"

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

first_deploy=$(operation_field first_deploy)
if [ "$first_deploy" = true ]; then
    "$repository_root/infra/scripts/bootstrap_database.sh" \
        "$environment_name" "$runtime_dir" "$release_sha" "$operation_id" \
        "$backup_root"
else
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
    if needs pre-migration-backup-completed; then
        "$repository_root/infra/scripts/backup_postgres.sh" \
            "$environment_name" "$active_runtime" "$active_sha" "$backup_root" \
            pre-migration "$operation_id"
        checkpoint pre-migration-backup-completed
    fi
fi

docker compose --env-file "$control_env" -f "$compose_file" pull django next worker

migration_started_now=false
if needs migration-started; then
    checkpoint migration-started
    migration_started_now=true
fi
if needs migration-completed; then
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

if needs application-healthy; then
    docker compose --env-file "$control_env" -f "$compose_file" up \
        -d --remove-orphans --wait \
        --wait-timeout "${ROLLOUT_WAIT_TIMEOUT_SECONDS:-180}"
    "$repository_root/infra/scripts/verify_application_rollout.sh" \
        "$runtime_dir" "$release_manifest" "$compose_file"
    checkpoint application-healthy
fi
