#!/bin/sh
set -eu

[ "$#" -eq 3 ] || {
    echo "usage: verify_application_rollout.sh <runtime-dir> <release-manifest> <application-compose>" >&2
    exit 2
}
runtime_dir=$1
release_manifest=$2
compose_file=$3
repository_root=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
control_env="$runtime_dir/control.env"

python3 "$repository_root/infra/scripts/validate_release_manifest.py" "$release_manifest"
django_image=$(python3 "$repository_root/infra/scripts/release_image.py" \
    "$release_manifest" django)
next_image=$(python3 "$repository_root/infra/scripts/release_image.py" \
    "$release_manifest" next)

docker compose --env-file "$control_env" -f "$compose_file" exec -T django \
    python -c "import urllib.request; q=urllib.request.Request('http://127.0.0.1:8000/api/readiness/',headers={'X-Forwarded-Proto':'https'}); r=urllib.request.urlopen(q,timeout=5); raise SystemExit(0 if r.status == 200 else 1)"
docker compose --env-file "$control_env" -f "$compose_file" exec -T django \
    python manage.py check --deploy
docker compose --env-file "$control_env" -f "$compose_file" exec -T next \
    node -e "fetch('http://127.0.0.1:3000/internal/health').then(r=>process.exit(r.status===200?0:1)).catch(()=>process.exit(1))"
docker compose --env-file "$control_env" -f "$compose_file" exec -T worker \
    python -c "import json,time,pathlib; d=json.loads(pathlib.Path('/tmp/kirillwynn-worker/heartbeat.json').read_text()); raise SystemExit(0 if time.time()-d['timestamp'] < 120 else 1)"
docker compose --env-file "$control_env" -f "$compose_file" exec -T worker \
    python -c "import os,urllib.request; p=urllib.request.HTTPErrorProcessor(); p.http_response=lambda q,r:r; p.https_response=p.http_response; r=urllib.request.build_opener(p).open(os.environ['WORKER_EGRESS_PROBE_URL'],timeout=10); raise SystemExit(0 if 100 <= r.status < 500 else 1)"

for service in django worker next; do
    container_id=$(docker compose --env-file "$control_env" -f "$compose_file" \
        ps -q "$service")
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
