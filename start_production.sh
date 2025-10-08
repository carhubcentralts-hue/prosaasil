#!/usr/bin/env bash
set -euo pipefail

export PYTHONUNBUFFERED=1
export PORT="${PORT:-5000}"
export FLASK_BASE_URL="${FLASK_BASE_URL:-http://127.0.0.1:5000}"
export BAILEYS_PORT="${BAILEYS_PORT:-3300}"
export RUN_MIGRATIONS_ON_START=1

echo "🚀 Starting AgentLocator Production System - Build #61"
echo "📊 Flask: 0.0.0.0:${PORT} | Baileys: 127.0.0.1:${BAILEYS_PORT}"
echo "✅ Build 61: Admin cross-tenant lead deletion + AI memory fixes"

# Ensure INTERNAL_SECRET is set (CRITICAL: Must come from environment!)
if [ -z "${INTERNAL_SECRET:-}" ]; then
    echo "❌ FATAL: INTERNAL_SECRET not found in environment!"
    echo "   Set INTERNAL_SECRET before running this script."
    echo "   Example: export INTERNAL_SECRET=\$(openssl rand -hex 32)"
    exit 1
fi
echo "✅ INTERNAL_SECRET found in environment"

# 1) Install Node dependencies and start Baileys (internal service)
echo "🟡 Installing Node dependencies for Baileys..."
cd services/whatsapp && npm install --omit=dev || npm ci --omit=dev || echo "⚠️ Could not install deps"
cd ../..

echo "🟡 Starting Baileys on port ${BAILEYS_PORT}..."
nohup node services/whatsapp/baileys_service.js > /tmp/baileys_prod.log 2>&1 &
BAI=$!
echo "✅ Baileys started (PID: $BAI)"

# 2) Start Flask with Uvicorn (ASGI server with WebSocket support)
echo "🟡 Starting Flask with Uvicorn on port ${PORT}..."
nohup uvicorn asgi:asgi_app --host 0.0.0.0 --port ${PORT} --ws websockets --lifespan off --timeout-keep-alive 75 > /tmp/flask_prod.log 2>&1 &
FL=$!
echo "✅ Flask/Uvicorn started (PID: $FL)"

echo "🎯 Both services running. System ready!"
echo "📊 Access: http://0.0.0.0:${PORT}"
echo "📝 Logs: /tmp/baileys_prod.log | /tmp/flask_prod.log"

# Give services time to fully start up before announcing ready
sleep 5
echo "🔍 Final status check..."
if kill -0 $BAI 2>/dev/null && kill -0 $FL 2>/dev/null; then
    echo "✅ All services confirmed running and ready!"
    echo "🔑 PIDs saved - Baileys: $BAI | Flask: $FL"
else
    echo "⚠️ One or more services may have issues - check logs"
    exit 1
fi

echo "✅ Startup complete - keeping processes alive..."
echo "💡 Press Ctrl+C to stop all services"

# Keep script alive and monitor processes
trap 'echo "🛑 Shutting down..."; kill $BAI $FL 2>/dev/null; exit 0' INT TERM

# Infinite loop to keep script alive and monitor processes
while true; do
    # Check if processes are still running
    if ! kill -0 $BAI 2>/dev/null; then
        echo "❌ Baileys died (PID $BAI) - restarting..."
        nohup node services/whatsapp/baileys_service.js >> /tmp/baileys_prod.log 2>&1 &
        BAI=$!
    fi
    
    if ! kill -0 $FL 2>/dev/null; then
        echo "❌ Flask died (PID $FL) - restarting..."
        nohup uvicorn asgi:asgi_app --host 0.0.0.0 --port ${PORT} --ws websockets --lifespan off --timeout-keep-alive 75 >> /tmp/flask_prod.log 2>&1 &
        FL=$!
    fi
    
    sleep 5
done