#!/bin/sh
set -eu

usage() {
    echo "usage: restore_postgres.sh <staging|production> <env-file> <dump> [target-db] [confirmation]" >&2
    exit 2
}

[ "$#" -ge 3 ] && [ "$#" -le 5 ] || usage
environment_name=$1
env_file=$2
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
if [ "$environment_name" = production ] && [ "$confirmation" != "RESTORE production $target_database" ]; then
    echo "production restore requires: RESTORE production $target_database" >&2
    exit 2
fi
[ -f "$dump_file" ] || { echo "dump file does not exist" >&2; exit 2; }

repository_root=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
database_user=$(python3 "$repository_root/infra/scripts/env_value.py" "$env_file" POSTGRES_USER)
project_name="kirillwynn-$environment_name"

docker compose \
    --project-name "$project_name" \
    --env-file "$env_file" \
    -f "$repository_root/infra/compose/application.yml" \
    exec -T postgres pg_restore --list < "$dump_file" > /dev/null

docker compose \
    --project-name "$project_name" \
    --env-file "$env_file" \
    -f "$repository_root/infra/compose/application.yml" \
    exec -T postgres createdb --username "$database_user" "$target_database"

docker compose \
    --project-name "$project_name" \
    --env-file "$env_file" \
    -f "$repository_root/infra/compose/application.yml" \
    exec -T postgres pg_restore \
    --username "$database_user" \
    --dbname "$target_database" \
    --exit-on-error \
    --no-owner \
    --no-acl < "$dump_file"

echo "restored into scratch database: $target_database"
