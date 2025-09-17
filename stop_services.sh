#!/bin/bash
# Stop all running services

echo "🛑 Stopping services..."

# Kill services using PID files if they exist
if [ -f flask.pid ]; then
    FLASK_PID=$(cat flask.pid)
    echo "Stopping Flask (PID: $FLASK_PID)..."
    kill $FLASK_PID 2>/dev/null || true
    rm flask.pid
fi

if [ -f baileys.pid ]; then
    BAILEYS_PID=$(cat baileys.pid)
    echo "Stopping Baileys (PID: $BAILEYS_PID)..."
    kill $BAILEYS_PID 2>/dev/null || true
    rm baileys.pid
fi

# Force kill any services on ports 5000 and 3001
echo "🧹 Cleaning up any remaining processes..."
lsof -ti:5000 | xargs -r kill -9 2>/dev/null || true
lsof -ti:3001 | xargs -r kill -9 2>/dev/null || true

echo "✅ All services stopped"