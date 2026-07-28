#!/bin/sh
set -eu

minimum=2.30.0
version=$(docker compose version --short)
version=${version#v}
version=${version%%-*}

awk -v actual="$version" '
BEGIN {
    if (actual !~ /^[0-9]+\.[0-9]+\.[0-9]+$/) exit 2
    split(actual, pieces, ".")
    if (pieces[1] > 2) exit 0
    if (pieces[1] < 2) exit 1
    if (pieces[2] > 30) exit 0
    if (pieces[2] < 30) exit 1
    exit (pieces[3] >= 0 ? 0 : 1)
}
' || {
    echo "Docker Compose >= $minimum is required for raw env_file support (found $version)" >&2
    exit 2
}
