#!/bin/sh
set -eu

[ "$#" -eq 2 ] || {
    echo "usage: ci_ssh_staging_stabilization_audit.sh <active-release-sha> <result-dir>" >&2
    exit 2
}
expected_release_sha=$1
result_dir=$2

: "${SERVER_HOST:?}"
: "${SERVER_USER:?}"
: "${SSH_PRIVATE_KEY:?}"
: "${SERVER_KNOWN_HOSTS:?}"
: "${GITHUB_RUN_ID:?}"
: "${GITHUB_RUN_ATTEMPT:?}"
: "${RUNNER_TEMP:?}"

case "$expected_release_sha" in
    *[!0-9a-f]*|"") exit 2 ;;
esac
test "${#expected_release_sha}" -eq 40
case "$GITHUB_RUN_ID:$GITHUB_RUN_ATTEMPT" in
    *[!0-9:]*|*:|:*|*:*:*) exit 2 ;;
esac

umask 077
mkdir -p "$result_dir"
ssh_dir=$RUNNER_TEMP/kirillwynn-stage18-audit-ssh
mkdir -p "$ssh_dir"
key_file=$ssh_dir/audit-key
known_hosts=$ssh_dir/known-hosts
bundle_file=$ssh_dir/staging-audit.tar.gz
printf '%s\n' "$SSH_PRIVATE_KEY" > "$key_file"
printf '%s\n' "$SERVER_KNOWN_HOSTS" > "$known_hosts"
chmod 600 "$key_file" "$known_hosts"

tar -czf "$bundle_file" infra/compose infra/scripts
remote_dir="/tmp/kirillwynn-stage18-audit-$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT"
remote_results="$remote_dir/results"
audit_operation_id="stage18-audit-$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT"
ssh_options="-i $key_file -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$known_hosts -o ConnectTimeout=15 -o ServerAliveInterval=15 -o ServerAliveCountMax=4"

cleanup_remote() {
    case "$remote_dir" in
        /tmp/kirillwynn-stage18-audit-[0-9]*-[0-9]*) ;;
        *) return ;;
    esac
    ssh $ssh_options "$SERVER_USER@$SERVER_HOST" \
        "rm -rf -- '$remote_dir'" \
        >/dev/null 2>&1 || true
}
trap cleanup_remote EXIT HUP INT TERM

ssh $ssh_options "$SERVER_USER@$SERVER_HOST" \
    "umask 077 && mkdir -p '$remote_dir/repository' '$remote_results'"
scp $ssh_options "$bundle_file" \
    "$SERVER_USER@$SERVER_HOST:$remote_dir/staging-audit.tar.gz"
ssh $ssh_options "$SERVER_USER@$SERVER_HOST" \
    "tar -xzf '$remote_dir/staging-audit.tar.gz' -C '$remote_dir/repository' && rm -f '$remote_dir/staging-audit.tar.gz' && chmod 700 '$remote_dir/repository/infra/scripts/run_staging_stabilization_audit_remote.sh'"

set +e
ssh $ssh_options "$SERVER_USER@$SERVER_HOST" \
    "'$remote_dir/repository/infra/scripts/run_staging_stabilization_audit_remote.sh' '$expected_release_sha' '$audit_operation_id' '$remote_results'"
audit_status=$?
set -e

scp $ssh_options -r "$SERVER_USER@$SERVER_HOST:$remote_results/." "$result_dir/" || {
    if [ "$audit_status" -eq 0 ]; then
        echo "staging audit passed remotely but evidence retrieval failed" >&2
        exit 2
    fi
}

if [ "$audit_status" -ne 0 ]; then
    echo "staging stabilization audit failed; retained output was retrieved when available" >&2
    exit "$audit_status"
fi

cleanup_remote
trap - EXIT HUP INT TERM
