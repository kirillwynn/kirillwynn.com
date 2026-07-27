#!/bin/sh
set -eu

[ "$#" -eq 3 ] || {
    echo "usage: ci_ssh_deploy.sh <staging|production> <runtime-env> <manifest>" >&2
    exit 2
}
environment_name=$1
runtime_env=$2
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
scp $ssh_options "$runtime_env" "$SERVER_USER@$SERVER_HOST:$remote_dir/runtime.env"
scp $ssh_options "$manifest" "$SERVER_USER@$SERVER_HOST:$remote_dir/release-manifest.json"
scp $ssh_options "$bundle_file" "$SERVER_USER@$SERVER_HOST:$remote_dir/infra.tar.gz"
ssh $ssh_options "$SERVER_USER@$SERVER_HOST" \
    "tar -xzf '$remote_dir/infra.tar.gz' -C '$remote_dir' && rm -f '$remote_dir/infra.tar.gz'"

if [ "$environment_name" = production ]; then
    ssh $ssh_options "$SERVER_USER@$SERVER_HOST" \
        "cd '$remote_dir' && infra/scripts/backup_postgres.sh production /srv/kirillwynn/runtime/production.env '$RELEASE_SHA'"
fi

ssh $ssh_options "$SERVER_USER@$SERVER_HOST" \
    "cd '$remote_dir' && infra/scripts/deploy_environment.sh '$environment_name' '$remote_dir/runtime.env' '$remote_dir/release-manifest.json'"

edge_runtime_env=/srv/kirillwynn/runtime/edge.env
if [ "$environment_name" = staging ]; then
    ssh $ssh_options "$SERVER_USER@$SERVER_HOST" \
        "cd '$remote_dir' && infra/scripts/verify_edge_candidate.sh '$remote_dir/release-manifest.json' '$edge_runtime_env'"
else
    ssh $ssh_options "$SERVER_USER@$SERVER_HOST" \
        "cd '$remote_dir' && infra/scripts/deploy_edge.sh '$remote_dir/release-manifest.json' '$edge_runtime_env'"
fi

cleanup_remote
trap - EXIT HUP INT TERM
