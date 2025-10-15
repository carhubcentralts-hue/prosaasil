#!/usr/bin/env bash
set -euo pipefail

export PYTHONUNBUFFERED=1
export PORT="${PORT:-5000}"
# ✅ BUILD 92: Fix FLASK_BASE_URL for production - Baileys needs to reach Flask
export FLASK_BASE_URL="${FLASK_BASE_URL:-http://localhost:5000}"
export BAILEYS_PORT="${BAILEYS_PORT:-3300}"
export RUN_MIGRATIONS_ON_START=1

echo "🚀 Starting AgentLocator Production System - Build #92"
echo "📊 EXTERNAL: Flask on 0.0.0.0:${PORT}"
echo "📊 INTERNAL: Baileys on 127.0.0.1:${BAILEYS_PORT}"
echo "✅ Build 92: WhatsApp Conversation Memory Fix - 10 Messages Full Context!"
echo "✅ Build 91: Multi-tenant WhatsApp - Business Routing"
echo "✅ Build 90: call_status NOT NULL Fix - All Calls Save"
echo "✅ Build 89: ImportError Fix - Lead Creation Thread"

# Auto-generate INTERNAL_SECRET if not set (for production deployment)
if [ -z "${INTERNAL_SECRET:-}" ]; then
    echo "⚠️ INTERNAL_SECRET not in environment - auto-generating..."
    export INTERNAL_SECRET=$(openssl rand -hex 32)
    echo "✅ INTERNAL_SECRET auto-generated"
else
    echo "✅ INTERNAL_SECRET found in environment"
fi

# 1) Install Node dependencies and start Baileys (internal service)
echo "🟡 Installing Node dependencies for Baileys..."
cd services/whatsapp && npm install --omit=dev || npm ci --omit=dev || echo "⚠️ Could not install deps"
cd ../..

echo "🟡 Starting Baileys on INTERNAL port 127.0.0.1:${BAILEYS_PORT}..."
BAILEYS_HOST=127.0.0.1 BAILEYS_PORT=${BAILEYS_PORT} nohup node services/whatsapp/baileys_service.js > /tmp/baileys_prod.log 2>&1 &
BAI=$!
echo "✅ Baileys started internally (PID: $BAI, 127.0.0.1:${BAILEYS_PORT})"

# 2) Start Flask/ASGI with Uvicorn on EXTERNAL port (native WebSocket support - BUILD 90)
echo "🟡 Starting BUILD 90 with Uvicorn ASGI on EXTERNAL port 0.0.0.0:${PORT}..."
uvicorn asgi:app --host 0.0.0.0 --port ${PORT} --ws websockets --lifespan off --timeout-keep-alive 75 --log-level info &
FL=$!
echo "✅ BUILD 90 Uvicorn/ASGI started (PID: $FL)"

echo "🎯 Both services running. System ready!"
echo "📊 EXTERNAL Access: Port ${PORT} (exposed)"
echo "📊 INTERNAL Baileys: 127.0.0.1:${BAILEYS_PORT} (not exposed)"
echo "📝 Logs: /tmp/baileys_prod.log"

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
        BAILEYS_HOST=127.0.0.1 BAILEYS_PORT=${BAILEYS_PORT} nohup node services/whatsapp/baileys_service.js >> /tmp/baileys_prod.log 2>&1 &
        BAI=$!
    fi
    
    if ! kill -0 $FL 2>/dev/null; then
        echo "❌ Flask/ASGI died (PID $FL) - restarting..."
        uvicorn asgi:app --host 0.0.0.0 --port ${PORT} --ws websockets --lifespan off --timeout-keep-alive 75 &
        FL=$!
    fi
    
    sleep 5
done