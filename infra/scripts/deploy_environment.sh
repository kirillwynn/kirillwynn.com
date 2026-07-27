#!/bin/sh
set -eu

usage() {
    echo "usage: deploy_environment.sh <staging|production> <runtime-env> <release-manifest>" >&2
    exit 2
}

[ "$#" -eq 3 ] || usage
environment_name=$1
incoming_env=$2
release_manifest=$3
case "$environment_name" in
    staging|production) ;;
    *) usage ;;
esac

repository_root=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
python3 "$repository_root/infra/scripts/validate_release_manifest.py" "$release_manifest"

release_sha=$(python3 "$repository_root/infra/scripts/env_value.py" "$incoming_env" RELEASE_SHA)
python3 "$repository_root/infra/scripts/validate_release_manifest.py" \
    "$release_manifest" --expect-sha "$release_sha"

runtime_dir=${RUNTIME_DIRECTORY:-/srv/kirillwynn/runtime}
umask 077
mkdir -p "$runtime_dir"
validated_env=$(mktemp "$runtime_dir/.${environment_name}.env.XXXXXX")
trap 'rm -f "$validated_env"' EXIT HUP INT TERM

python3 "$repository_root/infra/scripts/validate_runtime_env_file.py" \
    --environment "$environment_name" \
    --input "$incoming_env" \
    --output "$validated_env"
mv -f "$validated_env" "$runtime_dir/${environment_name}.env"
trap - EXIT HUP INT TERM

compose_file="$repository_root/infra/compose/application.yml"
project_name="kirillwynn-$environment_name"
runtime_env="$runtime_dir/${environment_name}.env"

django_image=$(python3 "$repository_root/infra/scripts/release_image.py" "$release_manifest" django)
next_image=$(python3 "$repository_root/infra/scripts/release_image.py" "$release_manifest" next)

export COMPOSE_PROJECT_NAME=$project_name
export RUNTIME_ENV_FILE=$runtime_env
export DJANGO_IMAGE=$django_image
export NEXT_IMAGE=$next_image

docker compose --env-file "$runtime_env" -f "$compose_file" pull django next worker
docker compose --env-file "$runtime_env" -f "$compose_file" run --rm django \
    python manage.py migrate --noinput
docker compose --env-file "$runtime_env" -f "$compose_file" up -d --remove-orphans
docker compose --env-file "$runtime_env" -f "$compose_file" exec -T django \
    python manage.py check --deploy
