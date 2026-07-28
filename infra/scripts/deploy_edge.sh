#!/bin/sh
set -eu

[ "$#" -eq 2 ] || {
    echo "usage: deploy_edge.sh <release-manifest> <edge-runtime-env>" >&2
    exit 2
}
release_manifest=$1
edge_runtime_env=$2
repository_root=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)

"$repository_root/infra/scripts/verify_edge_candidate.sh" \
    "$release_manifest" \
    "$edge_runtime_env"

EDGE_IMAGE=$(python3 "$repository_root/infra/scripts/release_image.py" "$release_manifest" edge)
export EDGE_IMAGE
docker compose \
    --env-file "$edge_runtime_env" \
    -f "$repository_root/infra/compose/edge.yml" \
    up -d --no-deps --wait --wait-timeout "${ROLLOUT_WAIT_TIMEOUT_SECONDS:-180}" edge
docker compose \
    --env-file "$edge_runtime_env" \
    -f "$repository_root/infra/compose/edge.yml" \
    exec -T edge nginx -t
edge_container=$(docker compose \
    --env-file "$edge_runtime_env" \
    -f "$repository_root/infra/compose/edge.yml" \
    ps -q edge)
test -n "$edge_container"
test "$(docker inspect --format '{{.Config.Image}}' "$edge_container")" = "$EDGE_IMAGE"
