#!/bin/sh
set -eu

repository_root=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
compose_file="$repository_root/infra/compose/integration.yml"
database_compose="$repository_root/infra/compose/database.yml"
test_root=$(mktemp -d)
bootstrap_control=
orphan_control=
cleanup() {
    docker compose --profile dynamic-edge -f "$compose_file" down --volumes --remove-orphans
    if [ -n "$bootstrap_control" ] && [ -f "$bootstrap_control" ]; then
        docker compose --env-file "$bootstrap_control" -f "$database_compose" \
            down --volumes --remove-orphans
    fi
    if [ -n "$orphan_control" ] && [ -f "$orphan_control" ]; then
        docker compose --env-file "$orphan_control" -f "$database_compose" \
            down --volumes --remove-orphans
    fi
    rm -rf "$test_root"
}
trap cleanup EXIT HUP INT TERM

"$repository_root/infra/scripts/require_compose_version.sh"
docker compose -f "$compose_file" up -d postgres minio minio-public mock-provider
docker compose -f "$compose_file" run --rm minio-init
docker compose -f "$compose_file" run --rm django \
    python manage.py migrate --noinput
docker compose -f "$compose_file" up -d --wait --wait-timeout 180 \
    django next worker edge

# Raw env values survive Compose byte-for-byte and role boundaries do not leak.
docker compose -f "$compose_file" exec -T next node -e \
    'const expected=["revalidation sentinel $ ","${UNCHANGED}"," # \"quotes\" ",String.fromCharCode(39),"single",String.fromCharCode(39)," \\ backslash and spaces"].join(""); if(process.env.REVALIDATION_SECRET!==expected)process.exit(1); for(const n of ["POSTGRES_PASSWORD","DJANGO_SECRET_KEY","S3_MEDIA_SECRET_ACCESS_KEY","GOOGLE_OAUTH_CLIENT_SECRET","GITHUB_OAUTH_CLIENT_SECRET","RESEND_API_KEY","RESEND_WEBHOOK_SECRET"])if(n in process.env)process.exit(2)'
docker compose -f "$compose_file" exec -T postgres sh -ec \
    'test "$POSTGRES_PASSWORD" = "postgres sentinel \$ \${UNCHANGED} # \"quotes\" '\''single'\'' \\ backslash and spaces"; for name in PUBLIC_SITE_URL GOOGLE_OAUTH_CLIENT_SECRET RESEND_API_KEY REVALIDATION_SECRET; do if env | grep -q "^${name}="; then exit 1; fi; done'
docker compose -f "$compose_file" exec -T worker python -c \
    "import os,urllib.request; r=urllib.request.urlopen(os.environ['WORKER_EGRESS_PROBE_URL'],timeout=5); assert r.status == 200"
if docker image inspect kirillwynn-next:ci --format '{{json .Config.Env}}' |
    grep -E 'POSTGRES_PASSWORD|DJANGO_SECRET_KEY|S3_MEDIA_SECRET_ACCESS_KEY|OAUTH_CLIENT_SECRET|RESEND_API_KEY|RESEND_WEBHOOK_SECRET|postgres sentinel|django sentinel'; then
    echo "Next image metadata contains a server secret" >&2
    exit 1
fi
docker run --rm --entrypoint sh kirillwynn-next:ci -ec \
    "! grep -R -E 'postgres sentinel|django sentinel|s3-only-integration-secret|google-only-integration-secret|github-only-integration-secret' /app/.next/static"

# S3-compatible upload/read URL uses the isolated integration bucket.
media_url=$(docker compose -f "$compose_file" exec -T django python -c \
    "from django.core.files.base import ContentFile; from django.core.files.storage import default_storage; name=default_storage.save('integration-proof.txt',ContentFile(b'minio-proof')); assert default_storage.open(name).read()==b'minio-proof'; print(default_storage.url(name),end='')")
curl --fail --silent --show-error --max-time 10 "$media_url" | grep -q minio-proof

# Exact routes, auth exceptions, and hidden internal health.
test "$(curl --silent --output /dev/null --write-out '%{http_code}' -H 'Host: staging.test' http://127.0.0.1:18080/)" = 401
curl --fail --silent --show-error --max-time 15 -u staging:integration \
    -H 'Host: staging.test' http://127.0.0.1:18080/api/health/ >/dev/null
curl --fail --silent --show-error --max-time 15 -u staging:integration \
    -H 'Host: staging.test' http://127.0.0.1:18080/api/readiness/ >/dev/null
curl --fail --silent --show-error --max-time 15 -u staging:integration \
    -H 'Host: staging.test' http://127.0.0.1:18080/ >/dev/null
curl --fail --silent --show-error --max-time 15 -u staging:integration \
    -H 'Host: staging.test' http://127.0.0.1:18080/bridge >/dev/null
test "$(curl --silent --output /dev/null --write-out '%{http_code}' -H 'Host: staging.test' -X POST http://127.0.0.1:18080/api/v1/email/webhooks/resend/)" != 401
test "$(curl --silent --output /dev/null --write-out '%{http_code}' -u staging:integration -H 'Host: staging.test' http://127.0.0.1:18080/media/missing)" = 404
test "$(curl --silent --output /dev/null --write-out '%{http_code}' -u staging:integration -H 'Host: staging.test' http://127.0.0.1:18080/internal/health)" = 404

# Edge starts with production absent; that host alone gets a bounded 502.
edge_id=$(docker compose -f "$compose_file" ps -q edge)
staging_started=$(date +%s)
test "$(curl --max-time 5 --silent --output /dev/null --write-out '%{http_code}' -H 'Host: production.test' http://127.0.0.1:18080/)" = 502
test "$(($(date +%s) - staging_started))" -lt 6
docker compose --profile dynamic-edge -f "$compose_file" up -d \
    production-django production-next
curl --retry 20 --retry-all-errors --retry-delay 1 --fail --silent --show-error \
    -H 'Host: production.test' http://127.0.0.1:18080/ >/dev/null
test "$edge_id" = "$(docker compose -f "$compose_file" ps -q edge)"

# Forwarded headers replace the untrusted chain and aliases never cross hosts.
forwarded=$(curl --fail --silent --show-error -H 'Host: production.test' \
    -H 'X-Forwarded-For: attacker.invalid' -H 'X-Forwarded-Proto: http' \
    http://127.0.0.1:18080/api/health/)
printf '%s' "$forwarded" | python3 -c \
    "import json,sys; d=json.load(sys.stdin); assert d['name']=='production-django'; h=d['headers']; assert h['host']=='production.test'; assert h['x-forwarded-proto']=='https'; assert h['x-forwarded-for']!='attacker.invalid'"

# Replacing staging app containers is discovered through Docker DNS without
# replacing edge; restart smoke remains healthy.
docker compose -f "$compose_file" up -d --force-recreate --wait --wait-timeout 180 \
    django next
test "$edge_id" = "$(docker compose -f "$compose_file" ps -q edge)"
curl --retry 20 --retry-all-errors --retry-delay 1 --fail --silent --show-error \
    -u staging:integration -H 'Host: staging.test' \
    http://127.0.0.1:18080/api/readiness/ >/dev/null
docker compose -f "$compose_file" restart django
curl --retry 20 --retry-all-errors --retry-delay 1 --fail --silent --show-error \
    -u staging:integration -H 'Host: staging.test' \
    http://127.0.0.1:18080/api/readiness/ >/dev/null

# Populated backup -> authenticated sidecar/checksum -> new scratch restore.
database_runtime="$test_root/database-runtime"
mkdir -p "$database_runtime"
cp "$repository_root/infra/tests/integration-env/postgres.env" "$database_runtime/postgres.env"
control_env="$database_runtime/control.env"
printf '%s\n' \
    'COMPOSE_PROJECT_NAME=kirillwynn-integration' \
    'POSTGRES_IMAGE=postgres:17.6-alpine' \
    "POSTGRES_ENV_FILE=$database_runtime/postgres.env" \
    'POSTGRES_VOLUME=kirillwynn-integration-postgres' \
    'DATABASE_NETWORK=kirillwynn-integration-database' > "$control_env"
docker compose -f "$compose_file" exec -T postgres sh -ec \
    'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "CREATE TABLE backup_proof (value text NOT NULL); INSERT INTO backup_proof VALUES ('\''populated'\'');"'
backup_dump=$("$repository_root/infra/scripts/backup_postgres.sh" \
    staging "$database_runtime" aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \
    "$test_root/backups" pre-migration integration-backup-operation)
"$repository_root/infra/scripts/restore_postgres.sh" \
    staging "$database_runtime" "$backup_dump" restore_integration
test "$(docker compose -f "$compose_file" exec -T postgres sh -ec \
    'psql -U "$POSTGRES_USER" -d restore_integration -Atc "SELECT value FROM backup_proof"')" = populated

tampered_dump="$test_root/tampered.dump"
cp "$backup_dump" "$tampered_dump"
cp "${backup_dump}.json" "${tampered_dump}.json"
python3 - "$tampered_dump" <<'PY'
import json
import sys
from pathlib import Path

dump = Path(sys.argv[1])
metadata = Path(f"{dump}.json")
payload = json.loads(metadata.read_text())
payload["dump_file"] = dump.name
metadata.write_text(json.dumps(payload))
with dump.open("ab") as handle:
    handle.write(b"tampered")
PY
if "$repository_root/infra/scripts/restore_postgres.sh" \
    staging "$database_runtime" "$tampered_dump" restore_tampered; then
    echo "tampered backup was accepted" >&2
    exit 1
fi
test "$(docker compose -f "$compose_file" exec -T postgres sh -ec \
    'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT count(*) FROM pg_database WHERE datname='\''restore_tampered'\''"')" = 0
missing_metadata="$test_root/missing.dump"
cp "$backup_dump" "$missing_metadata"
if "$repository_root/infra/scripts/restore_postgres.sh" \
    staging "$database_runtime" "$missing_metadata" restore_missing; then
    echo "backup without metadata was accepted" >&2
    exit 1
fi
tampered_metadata_dump="$test_root/tampered-metadata.dump"
cp "$backup_dump" "$tampered_metadata_dump"
python3 - "$backup_dump" "$tampered_metadata_dump" <<'PY'
import json
import sys
from pathlib import Path

source, dump = map(Path, sys.argv[1:])
payload = json.loads(Path(f"{source}.json").read_text())
payload["dump_file"] = dump.name
payload["sha256"] = "f" * 64
Path(f"{dump}.json").write_text(json.dumps(payload))
PY
if "$repository_root/infra/scripts/restore_postgres.sh" \
    staging "$database_runtime" "$tampered_metadata_dump" restore_bad_metadata; then
    echo "tampered backup metadata was accepted" >&2
    exit 1
fi

# First-production bootstrap rehearsal uses the real state and database
# operational scripts. A fault after the database-ready atomic replace mimics
# a lost SSH response; retrying the same operation does not recreate the
# volume or repeat a completed migration/backup phase.
postgres_digest=$(docker image inspect postgres:17.6-alpine --format '{{index .RepoDigests 0}}')
bootstrap_runtime="$test_root/production-runtime"
mkdir -p "$bootstrap_runtime"
printf '%s\n' \
    'POSTGRES_DB=kirillwynn_production_bootstrap' \
    'POSTGRES_USER=kirillwynn_production_bootstrap' \
    'POSTGRES_PASSWORD=bootstrap-only' > "$bootstrap_runtime/postgres.env"
bootstrap_control="$bootstrap_runtime/control.env"
printf '%s\n' \
    'COMPOSE_PROJECT_NAME=kirillwynn-production-bootstrap' \
    "POSTGRES_IMAGE=$postgres_digest" \
    "POSTGRES_ENV_FILE=$bootstrap_runtime/postgres.env" \
    'POSTGRES_VOLUME=kirillwynn-production-bootstrap-postgres' \
    'DATABASE_NETWORK=kirillwynn-production-bootstrap-database' > "$bootstrap_control"
bootstrap_manifest="$test_root/bootstrap-manifest.json"
python3 - "$bootstrap_manifest" <<'PY'
import json
import sys
from pathlib import Path

Path(sys.argv[1]).write_text(
    json.dumps(
        {
            "schema_version": 1,
            "release_sha": "b" * 40,
            "repository": "kirillwynn/kirillwynn.com",
            "built_at": "2026-07-27T00:00:00Z",
            "images": {
                "django": f"example/django@sha256:{'1' * 64}",
                "next": f"example/next@sha256:{'2' * 64}",
                "edge": f"example/edge@sha256:{'3' * 64}",
            },
        }
    )
)
PY
bootstrap_state="$test_root/bootstrap-state"
bootstrap_operation=bootstrap-production-integration
python3 "$repository_root/infra/scripts/record_rollout_state.py" begin \
    --environment production \
    --operation-id "$bootstrap_operation" \
    --operation deploy \
    --release-sha bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb \
    --deployment-sequence 1 \
    --runtime-directory "$bootstrap_runtime" \
    --manifest "$bootstrap_manifest" \
    --state-directory "$bootstrap_state"
if STATE_DIRECTORY="$bootstrap_state" \
    ROLLOUT_STATE_FAULT=checkpoint-bootstrap-database-ready:after-replace \
    "$repository_root/infra/scripts/bootstrap_database.sh" \
        production "$bootstrap_runtime" \
        bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb \
        "$bootstrap_operation" "$test_root/bootstrap-backups"; then
    echo "fault-injected bootstrap unexpectedly succeeded" >&2
    exit 1
fi
STATE_DIRECTORY="$bootstrap_state" \
    "$repository_root/infra/scripts/bootstrap_database.sh" \
    production "$bootstrap_runtime" \
    bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb \
    "$bootstrap_operation" "$test_root/bootstrap-backups"
test "$(docker compose --env-file "$bootstrap_control" -f "$database_compose" ps --services --filter status=running)" = postgres
test "$(find "$test_root/bootstrap-backups/production" -name '*.dump' | wc -l | tr -d ' ')" = 1
python3 - "$bootstrap_state/production/rollout-state.json" \
    "$test_root/bootstrap-backups/production" <<'PY'
import json
import sys
from pathlib import Path

state = json.loads(Path(sys.argv[1]).read_text())
attempt = state["attempts"]["bootstrap-production-integration"]
assert attempt["phase"] == "initial-backup-completed"
metadata = json.loads(next(Path(sys.argv[2]).glob("*.dump.json")).read_text())
assert metadata["backup_kind"] == "initial-empty"
assert metadata["operation_id"] == "bootstrap-production-integration"
PY

# An already-existing volume with only a new attempt-recorded state is not
# adopted or declared empty.
orphan_runtime="$test_root/orphan-runtime"
mkdir -p "$orphan_runtime"
cp "$bootstrap_runtime/postgres.env" "$orphan_runtime/postgres.env"
orphan_control="$orphan_runtime/control.env"
printf '%s\n' \
    'COMPOSE_PROJECT_NAME=kirillwynn-production-orphan' \
    "POSTGRES_IMAGE=$postgres_digest" \
    "POSTGRES_ENV_FILE=$orphan_runtime/postgres.env" \
    'POSTGRES_VOLUME=kirillwynn-production-orphan-postgres' \
    'DATABASE_NETWORK=kirillwynn-production-orphan-database' > "$orphan_control"
docker volume create kirillwynn-production-orphan-postgres >/dev/null
orphan_state="$test_root/orphan-state"
python3 "$repository_root/infra/scripts/record_rollout_state.py" begin \
    --environment production \
    --operation-id orphan-production-integration \
    --operation deploy \
    --release-sha bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb \
    --deployment-sequence 1 \
    --runtime-directory "$orphan_runtime" \
    --manifest "$bootstrap_manifest" \
    --state-directory "$orphan_state"
if STATE_DIRECTORY="$orphan_state" \
    "$repository_root/infra/scripts/bootstrap_database.sh" \
    production "$orphan_runtime" \
    bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb \
    orphan-production-integration "$test_root/orphan-backups"; then
    echo "existing unbound PostgreSQL volume was adopted" >&2
    exit 1
fi
test ! -d "$test_root/orphan-backups/production"
