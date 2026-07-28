#!/bin/sh
set -eu

[ "$#" -eq 8 ] || {
    echo "usage: resolve_failed_rollout.sh <staging|production> <failed-operation-id> <resolution-operation-id> <deployment-sequence> <retry|fix-forward> <runtime-dir> <release-manifest> <edge-runtime-env>" >&2
    exit 2
}
environment_name=$1
failed_operation_id=$2
operation_id=$3
deployment_sequence=$4
resolution_kind=$5
runtime_dir=$6
release_manifest=$7
edge_runtime_env=$8
case "$environment_name" in
    staging|production) ;;
    *) exit 2 ;;
esac
case "$resolution_kind" in
    retry|fix-forward) ;;
    *) exit 2 ;;
esac

repository_root=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)

# This entrypoint is intentionally separate from ordinary deployment. The
# state transition atomically transfers reviewed ownership of the failed
# attempt before any database, application, or edge mutation.
"$repository_root/infra/scripts/deploy_environment.sh" \
    "$environment_name" "$runtime_dir" "$release_manifest" "$operation_id" \
    "$resolution_kind" "$failed_operation_id" "$deployment_sequence"
"$repository_root/infra/scripts/advance_edge_rollout.sh" \
    "$environment_name" "$operation_id" "$release_manifest" "$edge_runtime_env"
echo "$resolution_kind resolution is pending reviewed public smoke"
