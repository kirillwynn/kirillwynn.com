#!/bin/sh
set -eu

usage() {
    echo "usage: restore_postgres.sh <staging|production> <runtime-dir> <dump> [target-db] [confirmation]" >&2
    exit 2
}

[ "$#" -ge 3 ] && [ "$#" -le 5 ] || usage
environment_name=$1
runtime_dir=$2
dump_file=$3
target_database=${4:-restore_$(date -u +%Y%m%dT%H%M%SZ)}
confirmation=${5:-}
case "$environment_name" in
    staging|production) ;;
    *) usage ;;
esac
case "$target_database" in
    restore_) echo "restore target requires a suffix" >&2; exit 2 ;;
    restore_*) ;;
    *) echo "restore target must be a new restore_* scratch database" >&2; exit 2 ;;
esac
case "$target_database" in
    *[!A-Za-z0-9_]*) echo "restore target contains unsupported characters" >&2; exit 2 ;;
esac
if [ "$environment_name" = production ] &&
    [ "$confirmation" != "RESTORE production $target_database" ]; then
    echo "production restore requires: RESTORE production $target_database" >&2
    exit 2
fi

repository_root=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
control_env="$runtime_dir/control.env"
postgres_env="$runtime_dir/postgres.env"
test -r "$control_env" && test -r "$postgres_env" || {
    echo "database runtime contract is incomplete" >&2
    exit 2
}

# Metadata shape, source environment, sidecar filename, and SHA-256 are all
# authenticated before pg_restore validation or any createdb side effect.
python3 "$repository_root/infra/scripts/verify_backup_metadata.py" \
    "$environment_name" "$dump_file"
"$repository_root/infra/scripts/require_compose_version.sh"
database_user=$(python3 "$repository_root/infra/scripts/env_value.py" "$postgres_env" POSTGRES_USER)

docker compose \
    --env-file "$control_env" \
    -f "$repository_root/infra/compose/database.yml" \
    exec -T postgres pg_restore --list < "$dump_file" > /dev/null
docker compose \
    --env-file "$control_env" \
    -f "$repository_root/infra/compose/database.yml" \
    exec -T postgres createdb --username "$database_user" "$target_database"
docker compose \
    --env-file "$control_env" \
    -f "$repository_root/infra/compose/database.yml" \
    exec -T postgres pg_restore \
    --username "$database_user" \
    --dbname "$target_database" \
    --exit-on-error \
    --no-owner \
    --no-acl < "$dump_file"

echo "restored into scratch database: $target_database"
