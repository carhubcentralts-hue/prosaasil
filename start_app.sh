#!/bin/bash
# Simple stable server startup script

set -e

export PORT=5000
export PYTHONPATH=.
export PYTHONUNBUFFERED=1

echo "🚀 Starting server on port 5000..."
echo "📍 Process PID: $$"
echo "🌐 Server will be available at: http://0.0.0.0:5000"
echo "📋 Health check: http://127.0.0.1:5000/healthz"
echo ""

# Start gunicorn directly (no nohup, no background)
exec gunicorn -k eventlet -w 1 wsgi:app --bind 0.0.0.0:5000 --timeout 120 --preload