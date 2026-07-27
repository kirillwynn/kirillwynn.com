#!/bin/sh
set -eu

[ "$#" -eq 3 ] || {
    echo "usage: prune_backups.sh <staging|production> <retention-days> <backup-root>" >&2
    exit 2
}
environment_name=$1
retention_days=$2
backup_root=$3
case "$environment_name" in
    staging|production) ;;
    *) exit 2 ;;
esac
case "$retention_days" in
    *[!0-9]*|"") exit 2 ;;
esac
[ "$retention_days" -ge 1 ] || exit 2
target="$backup_root/$environment_name"
[ -d "$target" ] || exit 0
find "$target" -type f \( -name '*.dump' -o -name '*.dump.json' \) \
    -mtime "+$retention_days" -print -delete
