#!/bin/sh
set -e

echo "Setting environment..."
export FLASK_APP=app
export FLASK_ENV=production

echo "Starting Gunicorn..."
exec gunicorn --bind 0.0.0.0:5000 app.wsgi:app
