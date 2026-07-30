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

active_release_sha=$(
    python3 "$state_tool" inspect \
        --environment staging \
        --field active.application.release_sha
)
test "$active_release_sha" = "$expected_release_sha" || {
    echo "the expected expansion release is not active on staging" >&2
    exit 1
}

run_sync() {
    output_file=$1
    shift
    docker compose \
        --env-file "$control_env" \
        -f "$compose_file" \
        run --rm --no-deps \
        -v "$input_dir:/private/input:ro" \
        django \
        python manage.py sync_reaction_catalog \
        --manifest /private/input/stage16-staging-v1.json \
        --attestation /private/input/reaction-catalog-attestation.json \
        --environment staging \
        "$@" > "$result_dir/$output_file"
}

exec 9>/srv/kirillwynn/locks/reaction-catalog.lock
flock -w 900 9
run_sync upload.txt
run_sync activate.txt --activate
run_sync idempotent.txt --activate
