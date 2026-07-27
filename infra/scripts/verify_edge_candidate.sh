#!/bin/sh
set -eu

[ "$#" -eq 2 ] || {
    echo "usage: verify_edge_candidate.sh <release-manifest> <edge-runtime-env>" >&2
    exit 2
}
release_manifest=$1
edge_runtime_env=$2
test -r "$edge_runtime_env" || {
    echo "edge runtime environment is not readable" >&2
    exit 2
}

repository_root=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
python3 "$repository_root/infra/scripts/validate_release_manifest.py" "$release_manifest"
EDGE_IMAGE=$(python3 "$repository_root/infra/scripts/release_image.py" "$release_manifest" edge)
export EDGE_IMAGE

docker compose \
    --env-file "$edge_runtime_env" \
    -f "$repository_root/infra/compose/edge.yml" \
    pull edge
docker compose \
    --env-file "$edge_runtime_env" \
    -f "$repository_root/infra/compose/edge.yml" \
    run --rm --no-deps edge nginx -t
