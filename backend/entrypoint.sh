#!/bin/sh

echo "Running Alembic migrations..."
alembic upgrade head

echo "Starting Gunicorn..."
exec gunicorn --bind 0.0.0.0:5000 app:app
