#!/bin/sh
set -eu

[ "$#" -eq 3 ] || {
    echo "usage: ci_ssh_deploy.sh <staging|production> <runtime-dir> <manifest>" >&2
    exit 2
}
environment_name=$1
runtime_dir=$2
manifest=$3
case "$environment_name" in
    staging|production) ;;
    *) exit 2 ;;
esac

: "${SERVER_HOST:?}"
: "${SERVER_USER:?}"
: "${SSH_PRIVATE_KEY:?}"
: "${SERVER_KNOWN_HOSTS:?}"
: "${RELEASE_SHA:?}"
case "$RELEASE_SHA" in
    *[!0-9a-f]*|"") exit 2 ;;
esac
test "${#RELEASE_SHA}" -eq 40
operation_id="deploy-${GITHUB_RUN_ID:?}-${environment_name}-${RELEASE_SHA}"

umask 077
ssh_dir=${RUNNER_TEMP:?}/kirillwynn-ssh
mkdir -p "$ssh_dir"
key_file="$ssh_dir/deploy-key"
known_hosts="$ssh_dir/known-hosts"
printf '%s\n' "$SSH_PRIVATE_KEY" > "$key_file"
printf '%s\n' "$SERVER_KNOWN_HOSTS" > "$known_hosts"
chmod 600 "$key_file" "$known_hosts"

case "${GITHUB_RUN_ID:?}:${GITHUB_RUN_ATTEMPT:?}" in
    *[!0-9:]*) echo "GitHub run identifiers must be numeric" >&2; exit 2 ;;
esac
remote_dir="/tmp/kirillwynn-deploy-${GITHUB_RUN_ID:?}-${GITHUB_RUN_ATTEMPT:?}"
ssh_options="-i $key_file -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$known_hosts"
cleanup_remote() {
    ssh $ssh_options "$SERVER_USER@$SERVER_HOST" \
        "rm -rf -- '$remote_dir'" \
        >/dev/null 2>&1 || true
}
trap cleanup_remote EXIT HUP INT TERM

ssh $ssh_options "$SERVER_USER@$SERVER_HOST" "umask 077 && mkdir -p '$remote_dir'"
bundle_file=${RUNNER_TEMP:?}/kirillwynn-infra.tar.gz
tar -czf "$bundle_file" infra/compose infra/scripts
scp $ssh_options "$manifest" "$SERVER_USER@$SERVER_HOST:$remote_dir/release-manifest.json"
scp $ssh_options -r "$runtime_dir" "$SERVER_USER@$SERVER_HOST:$remote_dir/runtime-input"
scp $ssh_options "$bundle_file" "$SERVER_USER@$SERVER_HOST:$remote_dir/infra.tar.gz"
ssh $ssh_options "$SERVER_USER@$SERVER_HOST" \
    "tar -xzf '$remote_dir/infra.tar.gz' -C '$remote_dir' && rm -f '$remote_dir/infra.tar.gz'"

ssh $ssh_options "$SERVER_USER@$SERVER_HOST" \
    "cd '$remote_dir' && infra/scripts/install_release_bundle.sh '$remote_dir/release-manifest.json' >/dev/null"
durable_release="/srv/kirillwynn/releases/$RELEASE_SHA"
durable_runtime="/srv/kirillwynn/runtime/releases/$RELEASE_SHA/$environment_name"
ssh $ssh_options "$SERVER_USER@$SERVER_HOST" \
    "cd '$durable_release' && if test -d '$durable_runtime'; then diff -qr '$remote_dir/runtime-input' '$durable_runtime' >/dev/null; else infra/scripts/validate_runtime_env_file.py --environment '$environment_name' --input-dir '$remote_dir/runtime-input' --output-dir '$durable_runtime'; fi"

edge_runtime_env=/srv/kirillwynn/runtime/edge.env
remote_rollout="infra/scripts/deploy_environment.sh '$environment_name' '$durable_runtime' '$durable_release/release-manifest.json' '$operation_id' && infra/scripts/advance_edge_rollout.sh '$environment_name' '$operation_id' '$durable_release/release-manifest.json' '$edge_runtime_env'"
ssh $ssh_options "$SERVER_USER@$SERVER_HOST" \
    "cd '$durable_release' && mkdir -p /srv/kirillwynn/locks && flock -w 900 /srv/kirillwynn/locks/release.lock sh -c \"$remote_rollout\""

smoke_passed=false
if [ "$environment_name" = staging ]; then
    : "${STAGING_BASIC_AUTH:?}"
    if curl --fail --silent --show-error --max-time 15 -u "$STAGING_BASIC_AUTH" \
        https://staging.kirillwynn.com/api/health/ >/dev/null &&
        curl --fail --silent --show-error --max-time 15 -u "$STAGING_BASIC_AUTH" \
            https://staging.kirillwynn.com/api/readiness/ >/dev/null &&
        curl --fail --silent --show-error --max-time 15 -u "$STAGING_BASIC_AUTH" \
            https://staging.kirillwynn.com/ >/dev/null; then
        smoke_passed=true
    fi
else
    if curl --fail --silent --show-error --max-time 15 \
        https://kirillwynn.com/api/health/ >/dev/null &&
        curl --fail --silent --show-error --max-time 15 \
            https://kirillwynn.com/api/readiness/ >/dev/null &&
        curl --fail --silent --show-error --max-time 15 \
            https://kirillwynn.com/ >/dev/null; then
        smoke_passed=true
    fi
fi
if [ "$smoke_passed" != true ]; then
    failure_command="cd '$durable_release' && flock -w 900 /srv/kirillwynn/locks/release.lock infra/scripts/mark_rollout_failed.sh '$environment_name' '$operation_id' 'GitHub runner public smoke failed'"
    ssh $ssh_options "$SERVER_USER@$SERVER_HOST" "$failure_command" ||
        ssh $ssh_options "$SERVER_USER@$SERVER_HOST" "$failure_command"
    echo "public smoke failed; reviewed recovery is required for $operation_id" >&2
    exit 1
fi

finalize_command="cd '$durable_release' && flock -w 900 /srv/kirillwynn/locks/release.lock infra/scripts/finalize_rollout.sh '$environment_name' '$operation_id'"
if ! ssh $ssh_options "$SERVER_USER@$SERVER_HOST" "$finalize_command"; then
    # A lost SSH response is indistinguishable from a completed atomic switch.
    # Retry the same immutable operation before classifying it as failed.
    if ! ssh $ssh_options "$SERVER_USER@$SERVER_HOST" "$finalize_command"; then
        ssh $ssh_options "$SERVER_USER@$SERVER_HOST" \
            "cd '$durable_release' && flock -w 900 /srv/kirillwynn/locks/release.lock infra/scripts/mark_rollout_failed.sh '$environment_name' '$operation_id' 'pre-activation live component re-attestation failed'"
        echo "final live attestation failed; reviewed recovery is required" >&2
        exit 1
    fi
fi
if [ "$environment_name" = staging ]; then
    python3 infra/scripts/create_attestation.py \
        "$manifest" "${ATTESTATION_OUTPUT:?}" "$operation_id"
fi

cleanup_remote
trap - EXIT HUP INT TERM
