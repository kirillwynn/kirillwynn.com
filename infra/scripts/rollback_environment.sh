#!/bin/sh
set -eu

[ "$#" -eq 1 ] || {
    echo "usage: rollback_environment.sh <staging|production>" >&2
    exit 2
}
environment_name=$1
case "$environment_name" in
    staging|production) ;;
    *) exit 2 ;;
esac

repository_root=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
state_root=${STATE_DIRECTORY:-/srv/kirillwynn/state}
runtime_root=${RUNTIME_DIRECTORY:-/srv/kirillwynn/runtime}
backup_root=${BACKUP_DIRECTORY:-/srv/kirillwynn/backups}
state_dir="$state_root/$environment_name"
active_state="$state_dir/active-release.json"
previous_manifest="$state_dir/previous-manifest.json"
test -r "$active_state" && test -r "$previous_manifest" || {
    echo "rollback requires active state and a previous durable manifest" >&2
    exit 2
}
if find "$state_dir" -maxdepth 1 -name 'pending-*.json' -print -quit | grep -q .; then
    echo "another rollout awaits public verification" >&2
    exit 2
fi

current_sha=$(python3 - "$active_state" <<'PY'
import json
import sys
print(json.load(open(sys.argv[1]))["release_sha"], end="")
PY
)
current_runtime=$(python3 - "$active_state" <<'PY'
import json
import sys
print(json.load(open(sys.argv[1]))["runtime_directory"], end="")
PY
)
current_sequence=$(python3 - "$active_state" <<'PY'
import json
import sys
print(json.load(open(sys.argv[1]))["deployment_sequence"], end="")
PY
)
rollback_sha=$(python3 - "$previous_manifest" <<'PY'
import json
import sys
print(json.load(open(sys.argv[1]))["release_sha"], end="")
PY
)
rollback_release=${RELEASE_DIRECTORY:-/srv/kirillwynn/releases}/"$rollback_sha"
rollback_manifest="$rollback_release/release-manifest.json"
rollback_runtime="$runtime_root/releases/$rollback_sha/$environment_name"
control_env="$rollback_runtime/control.env"
compose_file="$rollback_release/infra/compose/application.yml"
test -r "$rollback_manifest" && test -r "$control_env" || {
    echo "previous versioned bundle or runtime contract is missing" >&2
    exit 2
}
python3 "$repository_root/infra/scripts/validate_release_manifest.py" \
    "$rollback_manifest" --expect-sha "$rollback_sha"
test "$(python3 "$repository_root/infra/scripts/env_value.py" \
    "$current_runtime/control.env" POSTGRES_IMAGE)" = \
    "$(python3 "$repository_root/infra/scripts/env_value.py" \
    "$control_env" POSTGRES_IMAGE)" || {
    echo "rollback cannot change the PostgreSQL image" >&2
    exit 2
}

"$repository_root/infra/scripts/backup_postgres.sh" \
    "$environment_name" "$current_runtime" "$current_sha" "$backup_root"
docker compose --env-file "$control_env" -f "$compose_file" pull django next worker
# Rollback deliberately does not invoke migrate or reverse schema state.
docker compose --env-file "$control_env" -f "$compose_file" up \
    -d --remove-orphans --wait \
    --wait-timeout "${ROLLOUT_WAIT_TIMEOUT_SECONDS:-180}"
docker compose --env-file "$control_env" -f "$compose_file" exec -T django \
    python -c "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8000/api/readiness/',timeout=5); raise SystemExit(0 if r.status==200 else 1)"
docker compose --env-file "$control_env" -f "$compose_file" exec -T next \
    node -e "fetch('http://127.0.0.1:3000/internal/health').then(r=>process.exit(r.status===200?0:1)).catch(()=>process.exit(1))"
docker compose --env-file "$control_env" -f "$compose_file" exec -T worker \
    python -c "import json,time,pathlib; d=json.loads(pathlib.Path('/tmp/kirillwynn-worker/heartbeat.json').read_text()); raise SystemExit(0 if time.time()-d['timestamp']<120 else 1)"
docker compose --env-file "$control_env" -f "$compose_file" exec -T worker \
    python -c "import os,urllib.request; p=urllib.request.HTTPErrorProcessor(); p.http_response=lambda q,r:r; p.https_response=p.http_response; r=urllib.request.build_opener(p).open(os.environ['WORKER_EGRESS_PROBE_URL'],timeout=10); raise SystemExit(0 if 100<=r.status<500 else 1)"

django_image=$(python3 "$repository_root/infra/scripts/release_image.py" \
    "$rollback_manifest" django)
next_image=$(python3 "$repository_root/infra/scripts/release_image.py" \
    "$rollback_manifest" next)
for service in django worker next; do
    container_id=$(docker compose --env-file "$control_env" -f "$compose_file" ps -q "$service")
    actual_image=$(docker inspect --format '{{.Config.Image}}' "$container_id")
    case "$service" in
        django|worker) expected_image=$django_image ;;
        next) expected_image=$next_image ;;
    esac
    test "$actual_image" = "$expected_image"
done

next_sequence=$((current_sequence + 1))
python3 "$repository_root/infra/scripts/record_rollout_state.py" pending \
    --environment "$environment_name" \
    --release-sha "$rollback_sha" \
    --deployment-sequence "$next_sequence" \
    --runtime-directory "$rollback_runtime" \
    --manifest "$rollback_manifest" \
    --operation rollback \
    --state-directory "$state_root"
echo "rollback is pending public smoke; finalize only after external verification"
