#!/usr/bin/env bash
set -euo pipefail

export PYTHONUNBUFFERED=1
export PORT="${PORT:-5000}"
export FLASK_BASE_URL="${FLASK_BASE_URL:-http://127.0.0.1:5000}"
export BAILEYS_PORT="${BAILEYS_PORT:-3300}"

echo "🚀 Starting AgentLocator Production System"
echo "📊 Flask: 0.0.0.0:${PORT} | Baileys: 127.0.0.1:${BAILEYS_PORT}"

# Ensure INTERNAL_SECRET is set
if [ -z "${INTERNAL_SECRET:-}" ]; then
    echo "❌ INTERNAL_SECRET environment variable is required"
    exit 1
fi

# 1) Start Baileys (internal service)
echo "🟡 Starting Baileys on port ${BAILEYS_PORT}..."
node services/baileys/server.js &
BAI=$!
echo "✅ Baileys started (PID: $BAI)"

# 2) Start Flask (external listener)
echo "🟡 Starting Flask on port ${PORT}..."
gunicorn -w 1 -k eventlet -b 0.0.0.0:${PORT} wsgi:app &
FL=$!
echo "✅ Flask started (PID: $FL)"

# Keep both alive and cleanly shutdown
trap 'echo "🛑 Shutting down..."; kill -TERM $BAI $FL 2>/dev/null || true; wait || true' INT TERM
echo "🎯 Both services running. System ready!"
echo "📊 Access: http://0.0.0.0:${PORT}"

# Wait for both processes
while kill -0 $BAI 2>/dev/null && kill -0 $FL 2>/dev/null; do 
    sleep 2
done

echo "❌ One of the services stopped"