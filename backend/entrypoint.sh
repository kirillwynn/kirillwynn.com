#!/bin/sh

set -e

echo "Setting environment..."
export FLASK_APP=app
export FLASK_ENV=production

echo "Running Alembic upgrade (existing migrations)..."
flask db upgrade

echo "Autogenerating new Alembic migrations if needed..."
flask db migrate -m "Auto migration" || true

echo "Applying new Alembic migrations..."
flask db upgrade

echo "Starting Gunicorn..."
exec gunicorn --bind 0.0.0.0:5000 app.wsgi:app