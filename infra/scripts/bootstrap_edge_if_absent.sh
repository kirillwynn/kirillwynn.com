#!/bin/sh
set -eu

[ "$#" -eq 2 ] || {
    echo "usage: bootstrap_edge_if_absent.sh <release-manifest> <edge-runtime-env>" >&2
    exit 2
}
release_manifest=$1
edge_runtime_env=$2
repository_root=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)

test -r "$edge_runtime_env" || {
    echo "edge runtime environment is not readable" >&2
    exit 2
}

EDGE_IMAGE=$(python3 "$repository_root/infra/scripts/release_image.py" \
    "$release_manifest" edge)
export EDGE_IMAGE
edge_container=$(
    docker compose \
        --env-file "$edge_runtime_env" \
        -f "$repository_root/infra/compose/edge.yml" \
        ps -q edge
)
if [ -n "$edge_container" ]; then
    echo "shared_edge=existing"
    exit 0
fi

"$repository_root/infra/scripts/deploy_edge.sh" \
    "$release_manifest" \
    "$edge_runtime_env"
echo "shared_edge=started"
