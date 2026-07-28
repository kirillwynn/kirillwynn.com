#!/bin/sh
set -eu

[ "$#" -ge 1 ] && [ "$#" -le 2 ] || {
    echo "usage: install_release_bundle.sh <manifest> [release-root]" >&2
    exit 2
}
manifest=$1
release_root=${2:-${RELEASE_DIRECTORY:-/srv/kirillwynn/releases}}
repository_root=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
python3 "$repository_root/infra/scripts/validate_release_manifest.py" "$manifest"
release_sha=$(python3 - "$manifest" <<'PY'
import json
import sys
print(json.load(open(sys.argv[1]))["release_sha"], end="")
PY
)
target="$release_root/$release_sha"
if [ -d "$target" ]; then
    cmp "$manifest" "$target/release-manifest.json" >/dev/null || {
        echo "existing durable release has a different manifest" >&2
        exit 2
    }
    echo "$target"
    exit 0
fi

umask 077
mkdir -p "$release_root"
temporary=$(mktemp -d "$release_root/.${release_sha}.XXXXXX")
trap 'rm -rf "$temporary"' EXIT HUP INT TERM
mkdir -p "$temporary/infra"
cp -R "$repository_root/infra/compose" "$temporary/infra/compose"
cp -R "$repository_root/infra/scripts" "$temporary/infra/scripts"
cp "$manifest" "$temporary/release-manifest.json"
find "$temporary" -type d -exec chmod 0700 {} +
find "$temporary" -type f -exec chmod 0600 {} +
find "$temporary/infra/scripts" -type f -name '*.sh' -exec chmod 0700 {} +
find "$temporary/infra/scripts" -type f -name '*.py' -exec chmod 0700 {} +
python3 - "$temporary" <<'PY'
import os
import sys
from pathlib import Path

root = Path(sys.argv[1])
for path in sorted(root.rglob("*"), reverse=True):
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
descriptor = os.open(root, os.O_RDONLY)
try:
    os.fsync(descriptor)
finally:
    os.close(descriptor)
PY
mv "$temporary" "$target"
python3 - "$release_root" <<'PY'
import os
import sys

descriptor = os.open(sys.argv[1], os.O_RDONLY)
try:
    os.fsync(descriptor)
finally:
    os.close(descriptor)
PY
trap - EXIT HUP INT TERM
echo "$target"
