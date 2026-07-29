#!/bin/sh
set -eu

[ "$#" -eq 2 ] || {
    echo "usage: verify_active_edge.sh <release-manifest> <edge-runtime-env>" >&2
    exit 2
}
release_manifest=$1
edge_runtime_env=$2
repository_root=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)

EDGE_IMAGE=$(python3 "$repository_root/infra/scripts/release_image.py" \
    "$release_manifest" edge)
export EDGE_IMAGE
docker compose \
    --env-file "$edge_runtime_env" \
    -f "$repository_root/infra/compose/edge.yml" \
    exec -T edge nginx -t
docker compose \
    --env-file "$edge_runtime_env" \
    -f "$repository_root/infra/compose/edge.yml" \
    exec -T edge test -f /etc/nginx/auth/staging.htpasswd
docker compose \
    --env-file "$edge_runtime_env" \
    -f "$repository_root/infra/compose/edge.yml" \
    exec -T edge test -s /etc/nginx/auth/staging.htpasswd
edge_container=$(docker compose \
    --env-file "$edge_runtime_env" \
    -f "$repository_root/infra/compose/edge.yml" \
    ps -q edge)
test -n "$edge_container" || {
    echo "active edge container is missing" >&2
    exit 2
}
test "$(docker inspect --format '{{.Config.Image}}' "$edge_container")" = \
    "$EDGE_IMAGE" || {
    echo "active edge does not run the operation's exact digest" >&2
    exit 2
}
