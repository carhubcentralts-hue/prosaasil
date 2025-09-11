#!/bin/bash
echo "🚀 Starting AgentLocator Flask Server..."

# Set environment variables
export PYTHONUNBUFFERED=1
export PYTHONPATH=.
export PORT=${PORT:-5000}

# Kill any existing processes
pkill -f "python.*run_dev_server" 2>/dev/null || true
pkill -f "gunicorn.*wsgi" 2>/dev/null || true

echo "🔧 Starting Flask server on port $PORT..."

# Start the server
python3 run_dev_server.py