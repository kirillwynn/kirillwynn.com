#!/bin/sh
set -eu

rm -f /tmp/kirillwynn-cross-stack.sqlite3 /tmp/kirillwynn-cross-stack-state.json
.venv/bin/python manage.py migrate --noinput
.venv/bin/python tests/e2e/prepare_cross_stack.py
exec .venv/bin/python manage.py runserver 127.0.0.1:3201 --noreload --insecure
