#!/bin/sh
set -eu

usage() {
    echo "usage: deploy_environment.sh <staging|production> <runtime-dir> <release-manifest>" >&2
    exit 2
}

[ "$#" -eq 3 ] || usage
environment_name=$1
runtime_dir=$2
release_manifest=$3
case "$environment_name" in
    staging|production) ;;
    *) usage ;;
esac

repository_root=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
control_env="$runtime_dir/control.env"
compose_file="$repository_root/infra/compose/application.yml"
state_root=${STATE_DIRECTORY:-/srv/kirillwynn/state}
backup_root=${BACKUP_DIRECTORY:-/srv/kirillwynn/backups}
state_dir="$state_root/$environment_name"

"$repository_root/infra/scripts/require_compose_version.sh"
python3 "$repository_root/infra/scripts/validate_release_manifest.py" "$release_manifest"
release_sha=$(python3 "$repository_root/infra/scripts/env_value.py" "$control_env" RELEASE_SHA)
deploy_sequence=$(python3 "$repository_root/infra/scripts/env_value.py" "$control_env" DEPLOY_SEQUENCE)
python3 "$repository_root/infra/scripts/validate_release_manifest.py" \
    "$release_manifest" --expect-sha "$release_sha"

django_image=$(python3 "$repository_root/infra/scripts/release_image.py" "$release_manifest" django)
next_image=$(python3 "$repository_root/infra/scripts/release_image.py" "$release_manifest" next)
test "$django_image" = "$(python3 "$repository_root/infra/scripts/env_value.py" "$control_env" DJANGO_IMAGE)" || {
    echo "control Django image does not match release manifest" >&2
    exit 2
}
test "$next_image" = "$(python3 "$repository_root/infra/scripts/env_value.py" "$control_env" NEXT_IMAGE)" || {
    echo "control Next image does not match release manifest" >&2
    exit 2
}

umask 077
mkdir -p "$state_dir" "$backup_root"
if find "$state_dir" -maxdepth 1 -name 'pending-*.json' -print -quit | grep -q .; then
    echo "another rollout awaits public verification" >&2
    exit 2
fi
active_state="$state_dir/active-release.json"
if [ "$environment_name" = staging ] && [ -f "$active_state" ]; then
    python3 - "$active_state" "$deploy_sequence" "$release_sha" <<'PY'
import json
import sys

active = json.load(open(sys.argv[1]))
incoming_sequence = int(sys.argv[2])
if incoming_sequence < int(active["deployment_sequence"]):
    raise SystemExit("staging deployment sequence would roll main back")
if (
    incoming_sequence == int(active["deployment_sequence"])
    and sys.argv[3] != active["release_sha"]
):
    raise SystemExit("staging deployment sequence was already used by another SHA")
PY
fi

if [ -f "$active_state" ]; then
    active_sha=$(python3 - "$active_state" <<'PY'
import json
import sys
print(json.load(open(sys.argv[1]))["release_sha"], end="")
PY
)
    active_runtime=$(python3 - "$active_state" <<'PY'
import json
import sys
print(json.load(open(sys.argv[1]))["runtime_directory"], end="")
PY
)
    active_postgres_image=$(python3 "$repository_root/infra/scripts/env_value.py" \
        "$active_runtime/control.env" POSTGRES_IMAGE)
    incoming_postgres_image=$(python3 "$repository_root/infra/scripts/env_value.py" \
        "$control_env" POSTGRES_IMAGE)
    test "$active_postgres_image" = "$incoming_postgres_image" || {
        echo "PostgreSQL image changes require a separate reviewed database upgrade" >&2
        exit 2
    }
    "$repository_root/infra/scripts/backup_postgres.sh" \
        "$environment_name" "$active_runtime" "$active_sha" "$backup_root"
else
    # First production deploy creates only the pinned database service and
    # captures an empty initial backup before the first migration.
    "$repository_root/infra/scripts/bootstrap_database.sh" \
        "$environment_name" "$runtime_dir" "$release_sha" "$backup_root"
fi

docker compose --env-file "$control_env" -f "$compose_file" pull django next worker
docker compose --env-file "$control_env" -f "$compose_file" run --rm --no-deps django \
    python manage.py migrate --noinput
docker compose --env-file "$control_env" -f "$compose_file" up \
    -d --remove-orphans --wait \
    --wait-timeout "${ROLLOUT_WAIT_TIMEOUT_SECONDS:-180}"

docker compose --env-file "$control_env" -f "$compose_file" exec -T django \
    python -c "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8000/api/readiness/', timeout=5); raise SystemExit(0 if r.status == 200 else 1)"
docker compose --env-file "$control_env" -f "$compose_file" exec -T django \
    python manage.py check --deploy
docker compose --env-file "$control_env" -f "$compose_file" exec -T next \
    node -e "fetch('http://127.0.0.1:3000/internal/health').then(r=>process.exit(r.status===200?0:1)).catch(()=>process.exit(1))"
docker compose --env-file "$control_env" -f "$compose_file" exec -T worker \
    python -c "import json,time,pathlib; d=json.loads(pathlib.Path('/tmp/kirillwynn-worker/heartbeat.json').read_text()); raise SystemExit(0 if time.time()-d['timestamp'] < 120 else 1)"
docker compose --env-file "$control_env" -f "$compose_file" exec -T worker \
    python -c "import os,urllib.request; p=urllib.request.HTTPErrorProcessor(); p.http_response=lambda q,r:r; p.https_response=p.http_response; r=urllib.request.build_opener(p).open(os.environ['WORKER_EGRESS_PROBE_URL'],timeout=10); raise SystemExit(0 if 100 <= r.status < 500 else 1)"

for service in django worker next; do
    container_id=$(docker compose --env-file "$control_env" -f "$compose_file" ps -q "$service")
    test -n "$container_id" || {
        echo "$service container is missing after rollout" >&2
        exit 2
    }
    actual_image=$(docker inspect --format '{{.Config.Image}}' "$container_id")
    case "$service" in
        django|worker) expected_image=$django_image ;;
        next) expected_image=$next_image ;;
    esac
    test "$actual_image" = "$expected_image" || {
        echo "$service does not run the attested image digest" >&2
        exit 2
    }
done

python3 "$repository_root/infra/scripts/record_rollout_state.py" pending \
    --environment "$environment_name" \
    --release-sha "$release_sha" \
    --deployment-sequence "$deploy_sequence" \
    --runtime-directory "$runtime_dir" \
    --manifest "$release_manifest" \
    --state-directory "$state_root"
