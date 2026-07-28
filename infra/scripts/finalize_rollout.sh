#!/bin/sh
set -eu

[ "$#" -eq 2 ] || {
    echo "usage: finalize_rollout.sh <staging|production> <release-sha>" >&2
    exit 2
}
environment_name=$1
release_sha=$2
repository_root=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
python3 "$repository_root/infra/scripts/record_rollout_state.py" finalize \
    --environment "$environment_name" \
    --release-sha "$release_sha" \
    --state-directory "${STATE_DIRECTORY:-/srv/kirillwynn/state}"
