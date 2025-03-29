#!/bin/bash
set -e

echo "Running Alembic migrations..."
alembic -c migrations/alembic.ini upgrade head

echo "Starting Gunicorn..."
exec gunicorn --bind 0.0.0.0:5000 "app:app"
