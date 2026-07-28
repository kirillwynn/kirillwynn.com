#!/bin/sh
set -eu

: "${SERVER_HOST:?}"
: "${SERVER_USER:?}"
: "${SSH_PRIVATE_KEY:?}"
: "${SERVER_KNOWN_HOSTS:?}"
: "${GHCR_USERNAME:?}"
: "${GHCR_TOKEN:?}"
: "${GITHUB_RUN_ID:?}"
: "${GITHUB_RUN_ATTEMPT:?}"
: "${RUNNER_TEMP:?}"

case "$GHCR_USERNAME" in
    *[!A-Za-z0-9_-]*|"")
        echo "GHCR username contains unsupported characters" >&2
        exit 2
        ;;
esac
case "$GITHUB_RUN_ID:$GITHUB_RUN_ATTEMPT" in
    *[!0-9:]*)
        echo "GitHub run identifiers must be numeric" >&2
        exit 2
        ;;
esac

umask 077
ssh_dir=$RUNNER_TEMP/kirillwynn-preflight-ssh
mkdir -p "$ssh_dir"
key_file=$ssh_dir/deploy-key
known_hosts=$ssh_dir/known-hosts
printf '%s\n' "$SSH_PRIVATE_KEY" > "$key_file"
printf '%s\n' "$SERVER_KNOWN_HOSTS" > "$known_hosts"
chmod 600 "$key_file" "$known_hosts"

remote_dir="/tmp/kirillwynn-preflight-$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT"
remote_docker_config=$remote_dir/docker-config
ssh_options="-i $key_file -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$known_hosts"
cleanup_remote() {
    ssh $ssh_options "$SERVER_USER@$SERVER_HOST" \
        "rm -rf -- '$remote_dir'" \
        >/dev/null 2>&1 || true
}
trap cleanup_remote EXIT HUP INT TERM

ssh $ssh_options "$SERVER_USER@$SERVER_HOST" \
    "umask 077 && mkdir -p '$remote_docker_config'"
printf '%s' "$GHCR_TOKEN" |
    ssh $ssh_options "$SERVER_USER@$SERVER_HOST" \
        "DOCKER_CONFIG='$remote_docker_config' docker login ghcr.io --username '$GHCR_USERNAME' --password-stdin >/dev/null 2>&1"

ssh $ssh_options "$SERVER_USER@$SERVER_HOST" \
    "DOCKER_CONFIG='$remote_docker_config' docker info >/dev/null"
ssh $ssh_options "$SERVER_USER@$SERVER_HOST" sh -s \
    < infra/scripts/require_compose_version.sh

ssh $ssh_options "$SERVER_USER@$SERVER_HOST" sh -s <<'REMOTE'
set -eu

install -d -m 0700 \
    /srv/kirillwynn/runtime \
    /srv/kirillwynn/releases \
    /srv/kirillwynn/state/staging \
    /srv/kirillwynn/backups/staging \
    /srv/kirillwynn/locks

volume_state=absent
if docker volume inspect kirillwynn-staging-postgres >/dev/null 2>&1; then
    volume_state=present
fi
rollout_state=absent
if test -f /srv/kirillwynn/state/staging/rollout-state.json; then
    rollout_state=present
fi
if test "$volume_state" = present && test "$rollout_state" = absent; then
    echo "foreign staging PostgreSQL volume exists without rollout state" >&2
    exit 2
fi

printf 'compose_version=%s\n' "$(docker compose version --short)"
printf 'staging_postgres_volume=%s\n' "$volume_state"
printf 'staging_rollout_state=%s\n' "$rollout_state"
if test -f /srv/kirillwynn/state/production/rollout-state.json; then
    echo "production_rollout_state=present"
else
    echo "production_rollout_state=absent"
fi
df -Pk /srv/kirillwynn | awk 'NR == 2 { print "available_kib=" $4 }'
REMOTE

cleanup_remote
trap - EXIT HUP INT TERM
