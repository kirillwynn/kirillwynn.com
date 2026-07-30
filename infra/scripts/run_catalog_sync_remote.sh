#!/bin/sh
set -eu

[ "$#" -eq 3 ] || {
    echo "usage: run_catalog_sync_remote.sh <expected-release-sha> <input-dir> <result-dir>" >&2
    exit 2
}
expected_release_sha=$1
input_dir=$2
result_dir=$3
case "$expected_release_sha" in
    *[!0-9a-f]*|"") exit 2 ;;
esac
test "${#expected_release_sha}" -eq 40
transfer_directory=${input_dir%/input}
test "$transfer_directory/results" = "$result_dir"
case "$transfer_directory" in
    /tmp/kirillwynn-catalog-sync-[0-9]*-[0-9]*) ;;
    *) echo "catalog sync paths are outside the bounded transfer directory" >&2; exit 2 ;;
esac

release_directory="/srv/kirillwynn/releases/$expected_release_sha"
runtime_directory="/srv/kirillwynn/runtime/releases/$expected_release_sha/staging"
state_tool="$release_directory/infra/scripts/record_rollout_state.py"
compose_file="$release_directory/infra/compose/application.yml"
control_env="$runtime_directory/control.env"
test -f "$state_tool"
test -f "$compose_file"
test -f "$control_env"
test -f "$input_dir/stage16-staging-v1.json"
test -f "$input_dir/reaction-catalog-attestation.json"
test -d "$input_dir/objects"
mkdir -p "$result_dir" /srv/kirillwynn/locks
# The transfer parent remains mode 0700, while the read-only bind-mount root
# must be traversable by the non-root Django container user.
find "$input_dir" -type d -exec chmod 0755 {} +
find "$input_dir" -type f -exec chmod 0444 {} +

active_release_sha=$(
    python3 "$state_tool" inspect \
        --environment staging \
        --field active.application.release_sha
)
test "$active_release_sha" = "$expected_release_sha" || {
    echo "the expected expansion release is not active on staging" >&2
    exit 1
}

compose() {
    docker compose \
        --env-file "$control_env" \
        -f "$compose_file" \
        "$@"
}

catalog_database_snapshot() {
    compose exec -T postgres sh -ec '
        psql -X -v ON_ERROR_STOP=1 -At \
            -U "$POSTGRES_USER" \
            -d "$POSTGRES_DB" \
            -c "
                SELECT concat_ws(
                    chr(58),
                    (SELECT count(*) FROM discussions_reactioncatalogitem),
                    (SELECT count(*) FROM discussions_postreaction
                        WHERE catalog_item_id IS NULL AND length(emoji) > 0),
                    (SELECT count(*) FROM discussions_commentreaction
                        WHERE catalog_item_id IS NULL AND length(emoji) > 0)
                );
            "
    '
}

report_memory() {
    echo "staging catalog sync host memory:" >&2
    free -m >&2 || true
    if [ -r /sys/fs/cgroup/memory.events ]; then
        echo "staging catalog sync cgroup memory events:" >&2
        sed -n '/^oom /p;/^oom_kill /p;/^oom_group_kill /p' \
            /sys/fs/cgroup/memory.events >&2
    fi
    for service in postgres django next worker
    do
        container_id=$(compose ps -q "$service")
        if [ -n "$container_id" ]; then
            docker stats --no-stream \
                --format "$service {{.MemUsage}}" \
                "$container_id" >&2 || true
        fi
    done
}

worker_stopped=false
restore_worker() {
    [ "$worker_stopped" = true ] || return 0
    echo "restoring staging outbox worker" >&2
    compose up -d --no-deps worker >&2
    worker_container_id=$(compose ps -q worker)
    test -n "$worker_container_id"
    attempt=0
    while [ "$attempt" -lt 36 ]
    do
        worker_health=$(
            docker inspect \
                --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' \
                "$worker_container_id"
        )
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
trap restore_worker EXIT

run_sync() {
    output_file=$1
    shift
    echo "starting staging catalog sync phase: $output_file" >&2
    compose \
        run --rm --no-deps \
        -v "$input_dir:/private/input:ro" \
        django \
        python manage.py sync_reaction_catalog \
        --manifest /private/input/stage16-staging-v1.json \
        --attestation /private/input/reaction-catalog-attestation.json \
        --environment staging \
        "$@" > "$result_dir/$output_file"
    echo "completed staging catalog sync phase: $output_file" >&2
}

exec 9>/srv/kirillwynn/locks/reaction-catalog.lock
flock -w 900 9
database_snapshot_before=$(catalog_database_snapshot)
catalog_count_before=${database_snapshot_before%%:*}
case "$catalog_count_before" in
    0|228) ;;
    *) echo "unexpected pre-sync catalog row count" >&2; exit 1 ;;
esac
echo "pre-sync catalog/legacy DB counts: $database_snapshot_before" >&2
test "$(compose ps --services --filter status=running | grep -x worker)" = worker
report_memory
worker_stopped=true
compose stop --timeout 60 worker >&2
run_sync upload.txt
run_sync activate.txt --activate
run_sync idempotent.txt --activate
database_snapshot_after=$(catalog_database_snapshot)
catalog_count_after=${database_snapshot_after%%:*}
test "$catalog_count_after" = 228
test "${database_snapshot_after#*:}" = "${database_snapshot_before#*:}"
echo "post-sync catalog/legacy DB counts: $database_snapshot_after" >&2
restore_worker
trap - EXIT
report_memory
