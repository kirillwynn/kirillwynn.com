#!/bin/sh
set -eu

[ "$#" -eq 2 ] || {
    echo "usage: ci_ssh_catalog_sync.sh <input-dir> <result-dir>" >&2
    exit 2
}
input_dir=$1
result_dir=$2
: "${SERVER_HOST:?}"
: "${SERVER_USER:?}"
: "${SSH_PRIVATE_KEY:?}"
: "${SERVER_KNOWN_HOSTS:?}"
: "${EXPECTED_ACTIVE_RELEASE_SHA:?}"
: "${EXPECTED_MANIFEST_SHA256:?}"
: "${EXPECTED_ATTESTATION_SHA256:?}"
: "${GITHUB_RUN_ID:?}"
: "${GITHUB_RUN_ATTEMPT:?}"

case "$GITHUB_RUN_ID:$GITHUB_RUN_ATTEMPT" in
    *[!0-9:]*) exit 2 ;;
esac
for digest in \
    "$EXPECTED_ACTIVE_RELEASE_SHA" \
    "$EXPECTED_MANIFEST_SHA256" \
    "$EXPECTED_ATTESTATION_SHA256"
do
    case "$digest" in
        *[!0-9a-f]*|"") exit 2 ;;
    esac
done
test "${#EXPECTED_ACTIVE_RELEASE_SHA}" -eq 40
test "${#EXPECTED_MANIFEST_SHA256}" -eq 64
test "${#EXPECTED_ATTESTATION_SHA256}" -eq 64
test -f "$input_dir/stage16-staging-v1.json"
test -f "$input_dir/reaction-catalog-attestation.json"
test -d "$input_dir/objects"
test "$(sha256sum "$input_dir/stage16-staging-v1.json" | cut -d ' ' -f 1)" = \
    "$EXPECTED_MANIFEST_SHA256"
test "$(sha256sum "$input_dir/reaction-catalog-attestation.json" | cut -d ' ' -f 1)" = \
    "$EXPECTED_ATTESTATION_SHA256"
mkdir -p "$result_dir"

umask 077
ssh_dir=${RUNNER_TEMP:?}/kirillwynn-catalog-ssh
mkdir -p "$ssh_dir"
key_file="$ssh_dir/deploy-key"
known_hosts="$ssh_dir/known-hosts"
printf '%s\n' "$SSH_PRIVATE_KEY" > "$key_file"
printf '%s\n' "$SERVER_KNOWN_HOSTS" > "$known_hosts"
chmod 600 "$key_file" "$known_hosts"

remote_dir="/tmp/kirillwynn-catalog-sync-$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT"
ssh_options="-i $key_file -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$known_hosts"
cleanup_remote() {
    case "$remote_dir" in
        /tmp/kirillwynn-catalog-sync-[0-9]*-[0-9]*) ;;
        *) return ;;
    esac
    ssh $ssh_options "$SERVER_USER@$SERVER_HOST" \
        "rm -rf -- '$remote_dir'" \
        >/dev/null 2>&1 || true
}
trap cleanup_remote EXIT HUP INT TERM

ssh $ssh_options "$SERVER_USER@$SERVER_HOST" \
    "umask 077 && mkdir -p '$remote_dir/input' '$remote_dir/results'"
scp $ssh_options -r "$input_dir/." "$SERVER_USER@$SERVER_HOST:$remote_dir/input/"
scp $ssh_options infra/scripts/run_catalog_sync_remote.sh \
    "$SERVER_USER@$SERVER_HOST:$remote_dir/run_catalog_sync_remote.sh"
ssh $ssh_options "$SERVER_USER@$SERVER_HOST" \
    "chmod 700 '$remote_dir/run_catalog_sync_remote.sh' && '$remote_dir/run_catalog_sync_remote.sh' '$EXPECTED_ACTIVE_RELEASE_SHA' '$remote_dir/input' '$remote_dir/results'"
scp $ssh_options "$SERVER_USER@$SERVER_HOST:$remote_dir/results/upload.txt" \
    "$result_dir/upload.txt"
scp $ssh_options "$SERVER_USER@$SERVER_HOST:$remote_dir/results/activate.txt" \
    "$result_dir/activate.txt"
scp $ssh_options "$SERVER_USER@$SERVER_HOST:$remote_dir/results/idempotent.txt" \
    "$result_dir/idempotent.txt"

cleanup_remote
trap - EXIT HUP INT TERM
