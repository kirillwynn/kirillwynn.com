#!/bin/bash

echo "Running Alembic migrations..."
flask db upgrade

echo "Starting Gunicorn..."
exec gunicorn --bind 0.0.0.0:5000 app:app
