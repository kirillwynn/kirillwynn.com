#!/bin/sh
set -eu

repository_root=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
compose_file="$repository_root/infra/compose/integration.yml"
cleanup() {
    docker compose --profile integration -f "$compose_file" down --volumes --remove-orphans
}
trap cleanup EXIT HUP INT TERM

docker compose --profile integration -f "$compose_file" up -d postgres minio
docker compose --profile integration -f "$compose_file" run --rm django \
    python manage.py migrate --noinput
docker compose --profile integration -f "$compose_file" up -d --wait --wait-timeout 180 \
    django next worker edge

curl --fail --silent --show-error --max-time 15 http://127.0.0.1:18080/api/health/
curl --fail --silent --show-error --max-time 15 http://127.0.0.1:18080/api/readiness/
curl --fail --silent --show-error --max-time 15 http://127.0.0.1:18080/ >/dev/null
curl --fail --silent --show-error --max-time 15 http://127.0.0.1:18080/bridge >/dev/null
curl --fail --silent --show-error --max-time 15 http://127.0.0.1:18080/api/me/ >/dev/null
curl --fail --silent --show-error --max-time 15 http://127.0.0.1:18080/cms/ >/dev/null
test "$(curl --silent --output /dev/null --write-out '%{http_code}' http://127.0.0.1:18080/media/missing)" = 404
test "$(curl --silent --output /dev/null --write-out '%{http_code}' http://127.0.0.1:18080/internal/health)" = 404

docker compose --profile integration -f "$compose_file" run --rm worker \
    python manage.py run_worker --once
docker compose --profile integration -f "$compose_file" exec -T worker \
    python -c "import json,pathlib; json.loads(pathlib.Path('/tmp/kirillwynn-worker/heartbeat.json').read_text())"
docker compose --profile integration -f "$compose_file" restart django
curl --retry 20 --retry-all-errors --retry-delay 1 --fail --silent --show-error \
    http://127.0.0.1:18080/api/readiness/
