#!/bin/sh
set -eu

[ "$#" -ge 2 ] && [ "$#" -le 3 ] || {
    echo "usage: finalize_rollout.sh <staging|production> <operation-id> [edge-runtime-env]" >&2
    exit 2
}
environment_name=$1
operation_id=$2
edge_runtime_env=${3:-/srv/kirillwynn/runtime/edge.env}
repository_root=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
state_root=${STATE_DIRECTORY:-/srv/kirillwynn/state}
state_script="$repository_root/infra/scripts/record_rollout_state.py"

operation_field() {
    python3 "$state_script" inspect \
        --environment "$environment_name" \
        --operation-id "$operation_id" \
        --field "$1" \
        --state-directory "$state_root"
}

status=$(operation_field status)
if [ "$status" = completed ]; then
    exit 0
fi
test "$status" = in-progress && \
    test "$(operation_field phase)" = pending-public-smoke || {
    echo "operation is not pending successful public smoke" >&2
    exit 2
}

runtime_dir=$(operation_field candidate.application.runtime_directory)
release_manifest=$(operation_field candidate.application.manifest_path)
compose_file="$(dirname "$release_manifest")/infra/compose/application.yml"

# Re-attest actual component truth immediately before the one atomic state
# switch. This closes drift between the earlier internal gate and public smoke.
"$repository_root/infra/scripts/verify_application_rollout.sh" \
    "$runtime_dir" "$release_manifest" "$compose_file"
if [ "$environment_name" = production ]; then
    "$repository_root/infra/scripts/verify_active_edge.sh" \
        "$release_manifest" "$edge_runtime_env"
else
    "$repository_root/infra/scripts/verify_edge_candidate.sh" \
        "$release_manifest" "$edge_runtime_env"
fi

python3 "$state_script" finalize \
    --environment "$environment_name" \
    --operation-id "$operation_id" \
    --state-directory "$state_root"
