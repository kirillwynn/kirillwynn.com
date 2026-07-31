#!/bin/sh
set -eu

[ "$#" -eq 3 ] || {
    echo "usage: ci_ssh_mark_rollout_failed.sh staging <operation-id> <release-sha>" >&2
    exit 2
}
environment_name=$1
operation_id=$2
release_sha=$3
test "$environment_name" = staging || {
    echo "reviewed CI failure recording is staging-only" >&2
    exit 2
}
case "$operation_id" in
    *[!A-Za-z0-9._:-]*|"")
        echo "operation ID is invalid" >&2
        exit 2
        ;;
esac
test "${#operation_id}" -ge 8 && test "${#operation_id}" -le 128 || {
    echo "operation ID must contain 8-128 characters" >&2
    exit 2
}
case "$release_sha" in
    *[!0-9a-f]*|"")
        echo "release SHA is invalid" >&2
        exit 2
        ;;
esac
test "${#release_sha}" -eq 40 || {
    echo "release SHA must contain 40 hexadecimal characters" >&2
    exit 2
}

: "${SERVER_HOST:?}"
: "${SERVER_USER:?}"
: "${SSH_PRIVATE_KEY:?}"
: "${SERVER_KNOWN_HOSTS:?}"
: "${RUNNER_TEMP:?}"

umask 077
ssh_dir=$RUNNER_TEMP/kirillwynn-mark-failed-ssh
mkdir -p "$ssh_dir"
key_file=$ssh_dir/deploy-key
known_hosts=$ssh_dir/known-hosts
printf '%s\n' "$SSH_PRIVATE_KEY" > "$key_file"
printf '%s\n' "$SERVER_KNOWN_HOSTS" > "$known_hosts"
chmod 600 "$key_file" "$known_hosts"

ssh_options="-i $key_file -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$known_hosts -o ConnectTimeout=15 -o ServerAliveInterval=15 -o ServerAliveCountMax=4"
durable_release=/srv/kirillwynn/releases/$release_sha
state_script=infra/scripts/record_rollout_state.py
status=$(ssh $ssh_options "$SERVER_USER@$SERVER_HOST" \
    "cd '$durable_release' && python3 '$state_script' inspect --environment staging --operation-id '$operation_id' --field status --state-directory /srv/kirillwynn/state")
phase=$(ssh $ssh_options "$SERVER_USER@$SERVER_HOST" \
    "cd '$durable_release' && python3 '$state_script' inspect --environment staging --operation-id '$operation_id' --field phase --state-directory /srv/kirillwynn/state")
test "$status" = in-progress || {
    echo "rollout must be in-progress before reviewed failure recording" >&2
    exit 2
}
printf 'target_status=%s target_phase=%s\n' "$status" "$phase"

ssh $ssh_options "$SERVER_USER@$SERVER_HOST" \
    "cd '$durable_release' && flock -w 60 /srv/kirillwynn/locks/release.lock infra/scripts/mark_rollout_failed.sh staging '$operation_id' remote-rollout 'reviewed SSH disconnect left rollout pending'"
printf 'marked_failed_operation=%s\n' "$operation_id"
