#!/usr/bin/env bash
set -euo pipefail

export PYTHONUNBUFFERED=1
export PORT="${PORT:-5000}"
export FLASK_BASE_URL="${FLASK_BASE_URL:-http://127.0.0.1:5000}"
export BAILEYS_PORT="${BAILEYS_PORT:-3300}"
export RUN_MIGRATIONS_ON_START=1

echo "🚀 Starting AgentLocator Production System - Build #59"
echo "📊 Flask: 0.0.0.0:${PORT} | Baileys: 127.0.0.1:${BAILEYS_PORT}"
echo "✅ Build 59: Prompt cache invalidation + QR persistence fixes"

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
node services/whatsapp/baileys_service.js &
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

# Give services time to fully start up before announcing ready
sleep 3
echo "🔍 Final status check..."
if kill -0 $BAI 2>/dev/null && kill -0 $FL 2>/dev/null; then
    echo "✅ All services confirmed running and ready!"
else
    echo "⚠️ One or more services may have issues"
fi

# Wait for both processes
while kill -0 $BAI 2>/dev/null && kill -0 $FL 2>/dev/null; do 
    sleep 2
done

echo "❌ One of the services stopped"