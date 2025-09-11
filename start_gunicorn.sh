#!/bin/bash
# Startup script for gunicorn server with eventlet worker
set -e

export PORT=${PORT:-5000}
export PYTHONUNBUFFERED=1
export PYTHONPATH=.

echo "🚀 Starting gunicorn server on 0.0.0.0:$PORT"
echo "📋 Health endpoint: http://127.0.0.1:$PORT/healthz"
echo "🔍 Version endpoint: http://127.0.0.1:$PORT/version"

# Run the exact command from Procfile
exec gunicorn -k eventlet -w 1 wsgi:app --bind 0.0.0.0:${PORT} --timeout 120 --preload