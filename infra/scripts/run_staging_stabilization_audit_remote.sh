#!/bin/sh
set -eu

usage() {
    echo "usage: run_staging_stabilization_audit_remote.sh <active-release-sha> <audit-operation-id> <output-dir>" >&2
    exit 2
}

[ "$#" -eq 3 ] || usage
expected_release_sha=$1
audit_operation_id=$2
output_dir=$3

case "$expected_release_sha" in
    *[!0-9a-f]*|"") usage ;;
esac
[ "${#expected_release_sha}" -eq 40 ] || usage
case "$audit_operation_id" in
    stage18-audit-[0-9]*-[0-9]*) ;;
    *) usage ;;
esac
audit_identity=${audit_operation_id#stage18-audit-}
audit_run_id=${audit_identity%%-*}
audit_attempt=${audit_identity#*-}
case "$audit_run_id:$audit_attempt" in
    *[!0-9:]*|*:|:*|*:*:*) usage ;;
esac
case "$output_dir" in
    /tmp/kirillwynn-stage18-audit-[0-9]*-[0-9]*/results) ;;
    *) usage ;;
esac

if [ "${STAGE18_AUDIT_LOCK_HELD:-}" != 1 ]; then
    install -d -m 0700 /srv/kirillwynn/locks
    exec flock -w 900 /srv/kirillwynn/locks/release.lock \
        env STAGE18_AUDIT_LOCK_HELD=1 "$0" "$@"
fi

repository_root=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
state_root=/srv/kirillwynn/state
state_script="$repository_root/infra/scripts/record_rollout_state.py"
data_audit_script="$repository_root/infra/scripts/staging_data_audit.py"
performance_audit_script="$repository_root/infra/scripts/staging_performance_audit.py"
comparison_script="$repository_root/infra/scripts/compare_staging_data_audits.py"
release_audit_script="$repository_root/infra/scripts/staging_release_state_audit.py"
edge_runtime_env=/srv/kirillwynn/runtime/edge.env

test ! -L "$output_dir" || {
    echo "audit output directory must not be a symlink" >&2
    exit 2
}
umask 077
mkdir -p "$output_dir"
test -d "$output_dir" && test -O "$output_dir"
progress_file="$output_dir/audit-progress.txt"
: > "$progress_file"

record_phase() {
    printf 'phase=%s\n' "$1" >> "$progress_file"
}

state_field() {
    python3 "$state_script" inspect \
        --environment staging \
        --state-directory "$state_root" \
        --field "$1"
}

live_edge_container() {
    edge_container=$(docker ps --no-trunc -q \
        --filter label=com.docker.compose.project=kirillwynn-edge \
        --filter label=com.docker.compose.service=edge)
    case "$edge_container" in
        "") echo "active shared Edge container is missing" >&2; exit 2 ;;
        *'
'*) echo "multiple active shared Edge containers were found" >&2; exit 2 ;;
    esac
    printf '%s\n' "$edge_container"
}

test -r "$edge_runtime_env"
active_edge_container=$(live_edge_container)
active_edge_image=$(docker inspect --format '{{.Config.Image}}' \
    "$active_edge_container")
python3 "$release_audit_script" \
    --expected-active-release "$expected_release_sha" \
    --active-edge-image "$active_edge_image" \
    --state-directory "$state_root" \
    --output "$output_dir/release-state-before.json"
active_edge_manifest=$(python3 - "$output_dir/release-state-before.json" <<'PY'
import json
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text())
print(report["active_shared_edge"]["matching_manifests"][0]["manifest_path"])
PY
)

active_runtime=$(state_field active.application.runtime_directory)
active_manifest=$(state_field active.application.manifest_path)
active_release_root=$(dirname "$active_manifest")
application_compose="$active_release_root/infra/compose/application.yml"
database_compose="$active_release_root/infra/compose/database.yml"
control_env="$active_runtime/control.env"
postgres_env="$active_runtime/postgres.env"

for required_path in \
    "$active_runtime" \
    "$active_manifest" \
    "$active_edge_manifest" \
    "$application_compose" \
    "$database_compose" \
    "$edge_runtime_env" \
    "$control_env" \
    "$postgres_env"
do
    test -r "$required_path" || {
        echo "active staging runtime contract is incomplete" >&2
        exit 2
    }
done

diff -qr "$repository_root/infra/compose" "$active_release_root/infra/compose" \
    > "$output_dir/compose-drift.txt"
python3 - "$repository_root/infra/scripts" "$active_runtime" <<'PY'
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from validate_runtime_env_file import validated_directory

validated_directory("staging", Path(sys.argv[2]))
PY

"$repository_root/infra/scripts/verify_application_rollout.sh" \
    "$active_runtime" "$active_manifest" "$application_compose"
"$repository_root/infra/scripts/verify_active_edge.sh" \
    "$active_edge_manifest" "$edge_runtime_env"
record_phase release-state-verified

compose() {
    docker compose --env-file "$control_env" -f "$application_compose" "$@"
}

report_memory() {
    report_name=$1
    report_file="$output_dir/memory-$report_name.txt"
    awk '
        $1 == "MemTotal:" { print "memory_total_kib=" $2 }
        $1 == "MemAvailable:" { print "memory_available_kib=" $2 }
    ' /proc/meminfo > "$report_file"
    if [ -r /sys/fs/cgroup/memory.events ]; then
        sed -n '/^oom /p;/^oom_kill /p;/^oom_group_kill /p' \
            /sys/fs/cgroup/memory.events >> "$report_file"
    fi
    for memory_service in postgres django next worker
    do
        memory_container=$(compose ps -q "$memory_service")
        if [ -n "$memory_container" ]; then
            docker stats --no-stream \
                --format "$memory_service {{.MemUsage}}" \
                "$memory_container" >> "$report_file"
        fi
    done
}

worker_stopped=false
worker_container_before=
restore_worker() {
    [ "$worker_stopped" = true ] || return 0
    echo "restoring staging outbox worker" >&2
    compose start worker >&2
    worker_container_after=$(compose ps -q worker)
    test -n "$worker_container_after"
    test "$worker_container_after" = "$worker_container_before"
    attempt=0
    while [ "$attempt" -lt 36 ]
    do
        worker_health=$(docker inspect --format \
            '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' \
            "$worker_container_after")
        if [ "$worker_health" = healthy ]; then
            worker_stopped=false
            echo "staging outbox worker is healthy" >&2
            return 0
        fi
        test "$worker_health" != unhealthy
        attempt=$((attempt + 1))
        sleep 5
    done
    echo "staging outbox worker did not become healthy" >&2
    return 1
}

for service in postgres django worker next
do
    container_id=$(compose ps -q "$service")
    test -n "$container_id"
    health=$(docker inspect --format '{{.State.Health.Status}}' "$container_id")
    test "$health" = healthy || {
        echo "$service is not healthy" >&2
        exit 2
    }
    printf '%s_health=%s\n' "$service" "$health" >> "$output_dir/runtime-health.txt"
done
printf '%s\n' \
    'application_attestation=passed' \
    'active_edge_attestation=passed' \
    'runtime_contract=passed' \
    'committed_compose_drift=none' \
    >> "$output_dir/runtime-health.txt"
record_phase runtime-health-verified

production_containers=$(docker ps -aq \
    --filter label=com.docker.compose.project=kirillwynn-production)
test -z "$production_containers"
for production_object in \
    volume:kirillwynn-production-postgres \
    volume:kirillwynn-production-next-cache \
    network:kirillwynn-production-database \
    network:kirillwynn-production-application \
    network:kirillwynn-production-egress
do
    object_kind=${production_object%%:*}
    object_name=${production_object#*:}
    if docker "$object_kind" inspect "$object_name" >/dev/null 2>&1; then
        echo "unexpected production infrastructure object exists" >&2
        exit 2
    fi
done
production_edge_network=kirillwynn-production-edge
test "$(docker network inspect --format \
    '{{index .Labels "com.docker.compose.project"}}' \
    "$production_edge_network")" = kirillwynn-edge
test "$(docker network inspect --format \
    '{{index .Labels "com.docker.compose.network"}}' \
    "$production_edge_network")" = production_edge
production_edge_members=$(docker network inspect --format \
    '{{range $id, $container := .Containers}}{{println $id}}{{end}}' \
    "$production_edge_network")
test "$production_edge_members" = "$active_edge_container" || {
    echo "shared production-edge network has an unexpected attachment" >&2
    exit 2
}
test ! -e /srv/kirillwynn/state/production/rollout-state.json
printf '%s\n' \
    'production_rollout_state=absent' \
    'production_compose_containers=absent' \
    'production_database_volume=absent' \
    'production_next_cache_volume=absent' \
    'production_application_private_networks=absent' \
    'shared_production_edge_network=owned-by-shared-edge' \
    'shared_production_edge_network_attachments=active-edge-only' \
    > "$output_dir/production-boundary.txt"
record_phase production-boundary-verified

active_database=$(python3 "$repository_root/infra/scripts/env_value.py" \
    "$postgres_env" POSTGRES_DB)
case "$active_database" in
    kirillwynn_staging) ;;
    *) echo "active database identity is not staging" >&2; exit 2 ;;
esac

worker_container_before=$(compose ps -q worker)
test -n "$worker_container_before"
report_memory before-worker-pause
worker_stopped=true
trap restore_worker EXIT
compose stop --timeout 60 worker >&2
record_phase worker-paused
report_memory after-worker-pause

run_django() {
    target_database=$1
    shift
    compose run --rm --no-deps -T \
        -e "POSTGRES_DB=$target_database" \
        django "$@"
}

run_django "$active_database" python manage.py shell --no-imports \
    < "$data_audit_script" \
    > "$output_dir/data-active-before.json"
record_phase active-data-before-read

set +e
backup_dump=$(
    "$repository_root/infra/scripts/backup_postgres.sh" \
        staging "$active_runtime" "$expected_release_sha" \
        /srv/kirillwynn/backups manual "$audit_operation_id"
)
backup_status=$?
set -e
[ "$backup_status" -eq 0 ] || {
    echo "manual staging backup command failed with status $backup_status" >&2
    exit 2
}
case "$backup_dump" in
    /srv/kirillwynn/backups/staging/*.dump) ;;
    *) echo "manual backup path escaped the staging backup directory" >&2; exit 2 ;;
esac
test -f "$backup_dump" || {
    echo "manual staging backup dump is missing" >&2
    exit 2
}
test -f "$backup_dump.json" || {
    echo "manual staging backup metadata is missing" >&2
    exit 2
}
record_phase backup-created
python3 "$repository_root/infra/scripts/verify_backup_metadata.py" \
    staging "$backup_dump"
cp "$backup_dump.json" "$output_dir/backup-metadata.json"
record_phase backup-metadata-verified

set +e
docker compose --env-file "$control_env" -f "$database_compose" \
    exec -T postgres pg_restore --list \
    < "$backup_dump" \
    > "$output_dir/pg-restore-list.txt"
restore_list_status=$?
set -e
[ "$restore_list_status" -eq 0 ] || {
    echo "manual staging backup listing failed with status $restore_list_status" >&2
    exit 2
}
test -s "$output_dir/pg-restore-list.txt"
record_phase backup-restore-list-verified

restore_database="restore_stage18_${audit_run_id}_${audit_attempt}"
case "$restore_database" in
    restore_stage18_[0-9]*_[0-9]*) ;;
    *) echo "scratch database name is invalid" >&2; exit 2 ;;
esac
"$repository_root/infra/scripts/restore_postgres.sh" \
    staging "$active_runtime" "$backup_dump" "$restore_database" \
    > "$output_dir/restore.txt"
record_phase scratch-database-restored

run_django "$restore_database" python manage.py showmigrations --plan \
    > "$output_dir/restored-showmigrations.txt"
run_django "$restore_database" python manage.py migrate --plan \
    > "$output_dir/restored-migration-plan.txt"
run_django "$restore_database" python manage.py migrate --check
run_django "$restore_database" python manage.py check \
    > "$output_dir/restored-django-check.txt"
run_django "$restore_database" python manage.py check --deploy \
    > "$output_dir/restored-django-deploy-check.txt"
run_django "$restore_database" python manage.py makemigrations --check --dry-run \
    > "$output_dir/restored-makemigrations.txt"
record_phase restored-data-audit-started
run_django "$restore_database" python manage.py shell --no-imports \
    < "$data_audit_script" \
    > "$output_dir/data-restored.json"
record_phase restored-data-audit-verified
record_phase restored-performance-audit-started
run_django "$restore_database" python manage.py shell --no-imports \
    < "$performance_audit_script" \
    > "$output_dir/performance-restored.json"
record_phase restored-performance-audit-verified
record_phase restored-database-verified

run_django "$active_database" python manage.py shell --no-imports \
    < "$data_audit_script" \
    > "$output_dir/data-active-after.json"
python3 "$comparison_script" \
    "$output_dir/data-active-before.json" \
    "$output_dir/data-restored.json" \
    "$output_dir/data-active-after.json" \
    --output "$output_dir/data-comparison.json"
record_phase data-comparison-verified

restore_worker
trap - EXIT
record_phase worker-restored
report_memory after-worker-restore
"$repository_root/infra/scripts/verify_application_rollout.sh" \
    "$active_runtime" "$active_manifest" "$application_compose"
record_phase post-audit-runtime-health-verified

active_edge_container_after=$(live_edge_container)
test "$active_edge_container_after" = "$active_edge_container"
active_edge_image_after=$(docker inspect --format '{{.Config.Image}}' \
    "$active_edge_container_after")
test "$active_edge_image_after" = "$active_edge_image"
python3 "$release_audit_script" \
    --expected-active-release "$expected_release_sha" \
    --active-edge-image "$active_edge_image_after" \
    --state-directory "$state_root" \
    --output "$output_dir/release-state-after.json"
cmp "$output_dir/release-state-before.json" "$output_dir/release-state-after.json"
record_phase release-state-unchanged

printf 'scratch_database=%s\n' "$restore_database" > "$output_dir/recovery-summary.txt"
printf 'backup_file=%s\n' "$(basename "$backup_dump")" >> "$output_dir/recovery-summary.txt"
printf '%s\n' \
    'backup_metadata=verified' \
    'pg_restore_list=verified' \
    'restore_target=new-scratch-database' \
    'restored_database_public_attachment=none' \
    'restored_migration_plan=verified' \
    'restored_django_checks=passed' \
    'active_worker_pause=bounded-and-restored' \
    'post_audit_worker_heartbeat_egress=passed' \
    'active_database_replacement=none' \
    'scratch_database_retained=true' \
    >> "$output_dir/recovery-summary.txt"
record_phase complete
