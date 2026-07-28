#!/bin/sh
set -eu

[ "$#" -eq 4 ] || {
    echo "usage: advance_edge_rollout.sh <staging|production> <operation-id> <release-manifest> <edge-runtime-env>" >&2
    exit 2
}
environment_name=$1
operation_id=$2
release_manifest=$3
edge_runtime_env=$4
repository_root=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
state_root=${STATE_DIRECTORY:-/srv/kirillwynn/state}
state_script="$repository_root/infra/scripts/record_rollout_state.py"

needs() {
    python3 "$state_script" needs \
        --environment "$environment_name" \
        --operation-id "$operation_id" \
        --phase "$1" \
        --state-directory "$state_root"
}

checkpoint() {
    python3 "$state_script" checkpoint \
        --environment "$environment_name" \
        --operation-id "$operation_id" \
        --phase "$1" \
        --state-directory "$state_root"
}

status=$(python3 "$state_script" inspect \
    --environment "$environment_name" \
    --operation-id "$operation_id" \
    --field status \
    --state-directory "$state_root")
case "$status" in
    completed) exit 0 ;;
    failed)
        echo "failed rollout requires reviewed recovery" >&2
        exit 2
        ;;
    in-progress) ;;
    *) echo "rollout operation cannot advance edge" >&2; exit 2 ;;
esac

if [ "$environment_name" = production ]; then
    if needs edge-healthy; then
        "$repository_root/infra/scripts/deploy_edge.sh" \
            "$release_manifest" "$edge_runtime_env"
        checkpoint edge-healthy
    fi
else
    if needs edge-candidate-verified; then
        "$repository_root/infra/scripts/verify_edge_candidate.sh" \
            "$release_manifest" "$edge_runtime_env"
        checkpoint edge-candidate-verified
    fi
fi
if needs pending-public-smoke; then
    checkpoint pending-public-smoke
fi
