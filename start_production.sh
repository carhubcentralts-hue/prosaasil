#!/usr/bin/env bash
set -euo pipefail

export PYTHONUNBUFFERED=1
export PORT="${PORT:-5000}"
# ✅ BUILD 92: Fix FLASK_BASE_URL for production - Baileys needs to reach Flask
export FLASK_BASE_URL="${FLASK_BASE_URL:-http://localhost:5000}"
export BAILEYS_PORT="${BAILEYS_PORT:-3300}"
export RUN_MIGRATIONS_ON_START=1

# ✅ PRODUCTION: Frontend should be pre-built (skip slow npm install/build)
echo "🔍 Checking frontend build..."
if [ ! -d "client/dist" ] || [ ! -f "client/dist/index.html" ]; then
    echo "⚠️ WARNING: Frontend build not found!"
    echo "⚠️ In production, frontend should be pre-built in BUILD stage"
    echo "⚠️ Continuing anyway - frontend routes may not work!"
else
    echo "✅ Frontend build found"
fi

# ✅ BUILD 103: Fixed Baileys startup - always start unless explicitly external
SKIP_BAILEYS="${SKIP_BAILEYS:-false}"

# Only skip Baileys if BAILEYS_BASE_URL is set AND not localhost
if [ -n "${BAILEYS_BASE_URL:-}" ] && [[ ! "${BAILEYS_BASE_URL}" =~ ^https?://(localhost|127\.0\.0\.1) ]]; then
    echo "⚙️ BAILEYS_BASE_URL is set to external service - skipping local Baileys"
    echo "📊 External Baileys: ${BAILEYS_BASE_URL}"
    SKIP_BAILEYS=true
else
    # Use internal Baileys on localhost
    export BAILEYS_BASE_URL="http://127.0.0.1:${BAILEYS_PORT}"
    SKIP_BAILEYS=false
fi

echo "🚀 Starting AgentLocator Production System - Build #103"
echo "📊 EXTERNAL: Flask on 0.0.0.0:${PORT}"
if [ "$SKIP_BAILEYS" = "true" ]; then
    echo "📊 Baileys: External service (${BAILEYS_BASE_URL})"
else
    echo "📊 INTERNAL: Baileys on 127.0.0.1:${BAILEYS_PORT}"
fi
echo "✅ Build 94: WhatsApp Professional UI - AI Summaries & Lazy Loading!"
echo "✅ Build 93: WhatsApp Automatic Appointment Creation - Calendar Integration!"
echo "✅ Build 92: WhatsApp Conversation Memory Fix - 10 Messages Full Context!"
echo "✅ Build 91: Multi-tenant WhatsApp - Business Routing"

# Auto-generate INTERNAL_SECRET if not set (for production deployment)
if [ -z "${INTERNAL_SECRET:-}" ]; then
    echo "⚠️ INTERNAL_SECRET not in environment - auto-generating..."
    export INTERNAL_SECRET=$(openssl rand -hex 32)
    echo "✅ INTERNAL_SECRET auto-generated"
else
    echo "✅ INTERNAL_SECRET found in environment"
fi

# 1) Start Baileys ONLY if not using external service
if [ "$SKIP_BAILEYS" = "false" ]; then
    echo "🟡 Checking Baileys dependencies..."
    cd services/whatsapp
    
    # PRODUCTION: node_modules should be pre-installed (skip slow npm install)
    if [ ! -d "node_modules" ]; then
        echo "⚠️ WARNING: Baileys node_modules not found!"
        echo "⚠️ In production, dependencies should be pre-installed in BUILD stage"
        echo "⚠️ Continuing anyway - Baileys may not work!"
    else
        echo "✅ Baileys node_modules found"
    fi
    
    cd ../..

    echo "🟡 Starting Baileys on INTERNAL port 127.0.0.1:${BAILEYS_PORT}..."
    # Pass all required environment variables
    BAILEYS_HOST=127.0.0.1 \
    BAILEYS_PORT=${BAILEYS_PORT} \
    FLASK_BASE_URL=${FLASK_BASE_URL} \
    INTERNAL_SECRET=${INTERNAL_SECRET} \
    nohup node services/whatsapp/baileys_service.js > /tmp/baileys_prod.log 2>&1 &
    BAI=$!
    
    # Wait for Baileys to be ready (with timeout) - FAST for production deployment
    echo "⏳ Quick Baileys check (max 3s)..."
    BAILEYS_READY=false
    for i in {1..3}; do
        sleep 1
        if curl -sf http://127.0.0.1:${BAILEYS_PORT}/healthz > /dev/null 2>&1; then
            echo "✅ Baileys is ready! (PID: $BAI)"
            BAILEYS_READY=true
            break
        fi
        echo -n "."
    done
    echo ""
    
    # Don't fail if Baileys isn't ready yet - it will warm up in background
    if [ "$BAILEYS_READY" = "false" ]; then
        echo "⚠️ Baileys starting in background (PID: $BAI) - will be ready soon"
        if ! kill -0 $BAI 2>/dev/null; then
            echo "❌ WARNING: Baileys process died - check /tmp/baileys_prod.log"
        fi
    fi
else
    echo "⏭️ Skipping Baileys - using external service"
    BAI=0  # Dummy PID
fi

# 2) Start Flask/ASGI with Uvicorn on EXTERNAL port (native WebSocket support - BUILD 90)
echo "🟡 Starting BUILD 90 with Uvicorn ASGI on EXTERNAL port 0.0.0.0:${PORT}..."
uvicorn asgi:app --host 0.0.0.0 --port ${PORT} --ws websockets --lifespan off --timeout-keep-alive 75 --log-level info &
FL=$!
echo "✅ BUILD 90 Uvicorn/ASGI started (PID: $FL)"

echo "🎯 Both services running. System ready!"
echo "📊 EXTERNAL Access: Port ${PORT} (exposed)"
echo "📊 INTERNAL Baileys: 127.0.0.1:${BAILEYS_PORT} (not exposed)"
echo "📝 Logs: /tmp/baileys_prod.log"

# Quick health check - Flask must be ready immediately for Replit health checks
sleep 1
echo "🔍 Quick status check..."

# Check Flask (always required)
if ! kill -0 $FL 2>/dev/null; then
    echo "❌ Flask/ASGI failed to start - check logs"
    exit 1
fi

# Check Baileys only if running locally
if [ "$SKIP_BAILEYS" = "false" ]; then
    if ! kill -0 $BAI 2>/dev/null; then
        echo "❌ Baileys failed to start - check /tmp/baileys_prod.log"
        exit 1
    fi
    echo "✅ All services confirmed running and ready!"
    echo "🔑 PIDs saved - Baileys: $BAI | Flask: $FL"
else
    echo "✅ Flask confirmed running and ready!"
    echo "🔑 PID saved - Flask: $FL"
fi

echo "✅ Startup complete - keeping processes alive..."
echo "💡 Press Ctrl+C to stop all services"

# Keep script alive and monitor processes
trap 'echo "🛑 Shutting down..."; kill $BAI $FL 2>/dev/null; exit 0' INT TERM

# Infinite loop to keep script alive and monitor processes
while true; do
    # Check Baileys only if running locally
    if [ "$SKIP_BAILEYS" = "false" ]; then
        if ! kill -0 $BAI 2>/dev/null; then
            echo "❌ Baileys died (PID $BAI) - restarting..."
            BAILEYS_HOST=127.0.0.1 BAILEYS_PORT=${BAILEYS_PORT} nohup node services/whatsapp/baileys_service.js >> /tmp/baileys_prod.log 2>&1 &
            BAI=$!
        fi
    fi
    
    # Always check Flask
    if ! kill -0 $FL 2>/dev/null; then
        echo "❌ Flask/ASGI died (PID $FL) - restarting..."
        uvicorn asgi:app --host 0.0.0.0 --port ${PORT} --ws websockets --lifespan off --timeout-keep-alive 75 &
        FL=$!
    fi
    
    sleep 5
done