#!/bin/sh
set -eu

: "${SERVER_HOST:?}"
: "${SERVER_USER:?}"
: "${SSH_PRIVATE_KEY:?}"
: "${SERVER_KNOWN_HOSTS:?}"
: "${STAGING_BASIC_AUTH:?}"
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
case "$STAGING_BASIC_AUTH" in
    *'
'*)
        echo "staging Basic Auth credential must be single-line" >&2
        exit 2
        ;;
    *:*)
        auth_user=${STAGING_BASIC_AUTH%%:*}
        auth_password=${STAGING_BASIC_AUTH#*:}
        ;;
    *)
        echo "staging Basic Auth credential must use user:password format" >&2
        exit 2
        ;;
esac
case "$auth_user" in
    *[!A-Za-z0-9._-]*|"")
        echo "staging Basic Auth username contains unsupported characters" >&2
        exit 2
        ;;
esac
test -n "$auth_password" || {
    echo "staging Basic Auth password must not be empty" >&2
    exit 2
}
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
ssh_options="-i $key_file -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$known_hosts -o ConnectTimeout=15 -o ServerAliveInterval=15 -o ServerAliveCountMax=4"
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

auth_hash=$(printf '%s' "$auth_password" | openssl passwd -apr1 -stdin)
local_auth_file=$ssh_dir/staging.htpasswd
printf '%s:%s\n' "$auth_user" "$auth_hash" > "$local_auth_file"
chmod 600 "$local_auth_file"
scp $ssh_options "$local_auth_file" \
    "$SERVER_USER@$SERVER_HOST:$remote_dir/staging.htpasswd"
rm -f -- "$local_auth_file"
ssh $ssh_options "$SERVER_USER@$SERVER_HOST" \
    "set -eu; install -d -m 0755 /etc/nginx; test ! -d /etc/nginx/.htpasswd || { echo 'staging htpasswd path is a directory' >&2; exit 2; }; install -m 0640 -o 0 -g 101 '$remote_dir/staging.htpasswd' /etc/nginx/.htpasswd; test -f /etc/nginx/.htpasswd; test \"\$(stat -c '%u:%g:%a' /etc/nginx/.htpasswd)\" = '0:101:640'"

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
install -d -m 0755 /var/www/certbot/.well-known/acme-challenge
edge_runtime_tmp=/srv/kirillwynn/runtime/.edge.env.$$
trap 'rm -f -- "$edge_runtime_tmp"' EXIT HUP INT TERM
umask 077
printf '%s\n' \
    'STAGING_EDGE_NETWORK=kirillwynn-staging-edge' \
    'PRODUCTION_EDGE_NETWORK=kirillwynn-production-edge' \
    'LETSENCRYPT_DIR=/etc/letsencrypt' \
    'ACME_WEBROOT=/var/www/certbot' \
    'STAGING_HTPASSWD_FILE=/etc/nginx/.htpasswd' \
    > "$edge_runtime_tmp"
chmod 0600 "$edge_runtime_tmp"
mv -f -- "$edge_runtime_tmp" /srv/kirillwynn/runtime/edge.env
trap - EXIT HUP INT TERM

staging_fullchain=/etc/letsencrypt/live/staging.kirillwynn.com/fullchain.pem
staging_privkey=/etc/letsencrypt/live/staging.kirillwynn.com/privkey.pem
if ! test -s "$staging_fullchain" || ! test -s "$staging_privkey"; then
    command -v certbot >/dev/null || {
        echo "certbot is required to issue the staging certificate" >&2
        exit 2
    }
    listener_count=$(
        ss -H -ltn |
            awk '$4 ~ /:80$/ || $4 ~ /:443$/ { count += 1 } END { print count + 0 }'
    )
    test "$listener_count" -eq 0 || {
        echo "cannot use the standalone ACME challenge while ports 80/443 are in use" >&2
        exit 2
    }
    certbot certonly \
        --standalone \
        --preferred-challenges http \
        --non-interactive \
        --agree-tos \
        --keep-until-expiring \
        --cert-name staging.kirillwynn.com \
        -d staging.kirillwynn.com
fi

for tls_file in \
    "$staging_fullchain" \
    "$staging_privkey" \
    /etc/letsencrypt/live/kirillwynn.com/fullchain.pem \
    /etc/letsencrypt/live/kirillwynn.com/privkey.pem
do
    test -s "$tls_file" || {
        echo "required TLS material is missing: $tls_file" >&2
        exit 2
    }
done
test -f /etc/nginx/.htpasswd && test -s /etc/nginx/.htpasswd || {
    echo "staging htpasswd path is not a non-empty regular file" >&2
    exit 2
}

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
echo "tls_material=ready"
echo "acme_webroot=ready"
echo "staging_htpasswd=ready"
echo "edge_runtime=ready"
listener_count=$(
    ss -H -ltn |
        awk '$4 ~ /:80$/ || $4 ~ /:443$/ { count += 1 } END { print count + 0 }'
)
shared_edge_container=$(
    docker ps -q \
        --filter label=com.docker.compose.project=kirillwynn-edge \
        --filter label=com.docker.compose.service=edge
)
if test "$listener_count" -gt 0 && test -z "$shared_edge_container"; then
    echo "shared edge is absent while host ports 80/443 are allocated; reviewed ingress migration is required" >&2
    exit 2
fi
printf 'host_http_listeners=%s\n' "$listener_count"
if test -n "$shared_edge_container"; then
    echo "shared_edge=present"
else
    echo "shared_edge=absent"
fi
if test -f /srv/kirillwynn/state/production/rollout-state.json; then
    echo "production_rollout_state=present"
else
    echo "production_rollout_state=absent"
fi
df -Pk /srv/kirillwynn | awk 'NR == 2 { print "available_kib=" $4 }'
REMOTE

cleanup_remote
trap - EXIT HUP INT TERM
