#!/bin/bash
echo "🚀 Starting AgentLocator CRM System..."

# Set environment variables
export PYTHONUNBUFFERED=1
export PYTHONPATH=.
export EVENTLET_NO_GREENDNS=1
export EVENTLET_HUB=poll
export PORT=${PORT:-5000}

# Start the server
echo "🔧 Starting Gunicorn on port $PORT..."
python -m gunicorn wsgi:app -k eventlet -w 1 -b 0.0.0.0:$PORT --timeout 120 --keep-alive 75 --log-level info --access-logfile - --error-logfile -