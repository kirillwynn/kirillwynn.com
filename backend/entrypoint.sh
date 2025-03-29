#!/bin/sh
set -e

echo "Starting Gunicorn..."
exec gunicorn --bind 0.0.0.0:5000 app.wsgi:app
