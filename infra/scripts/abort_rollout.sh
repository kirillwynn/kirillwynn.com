#!/bin/sh
set -eu

[ "$#" -ge 2 ] && [ "$#" -le 3 ] || {
    echo "usage: abort_rollout.sh <staging|production> <operation-id> [reason]" >&2
    exit 2
}
environment_name=$1
operation_id=$2
reason=${3:-reviewed operator abort before runtime mutation}
repository_root=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
python3 "$repository_root/infra/scripts/record_rollout_state.py" abort \
    --environment "$environment_name" \
    --operation-id "$operation_id" \
    --reason "$reason" \
    --state-directory "${STATE_DIRECTORY:-/srv/kirillwynn/state}"
