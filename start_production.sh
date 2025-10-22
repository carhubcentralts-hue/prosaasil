#!/usr/bin/env bash
set -euo pipefail

export PYTHONUNBUFFERED=1
export PORT="${PORT:-5000}"
# ✅ BUILD 92: Fix FLASK_BASE_URL for production - Baileys needs to reach Flask
export FLASK_BASE_URL="${FLASK_BASE_URL:-http://localhost:5000}"
export BAILEYS_PORT="${BAILEYS_PORT:-3300}"
export RUN_MIGRATIONS_ON_START=1

# ✅ BUILD Frontend if not exists or is outdated
echo "🔍 Checking frontend build..."
if [ ! -d "client/dist" ] || [ ! -f "client/dist/index.html" ]; then
    echo "⚠️ Frontend build not found - building now..."
    cd client
    echo "📦 Installing frontend dependencies..."
    npm install --prefer-offline --no-audit --no-fund
    echo "🏗️ Building frontend with Vite..."
    npm run build
    cd ..
    echo "✅ Frontend build complete!"
else
    echo "✅ Frontend build found - skipping rebuild"
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
    echo "🟡 Installing Node dependencies for Baileys..."
    cd services/whatsapp
    
    # Try to install dependencies with verbose error handling
    if [ ! -d "node_modules" ] || [ ! -f "node_modules/.package-lock.json" ]; then
        echo "📦 Installing Node dependencies..."
        npm install --omit=dev --prefer-offline --no-audit --no-fund 2>&1 | tee /tmp/npm_install.log
        NPM_EXIT=$?
        if [ $NPM_EXIT -ne 0 ]; then
            echo "⚠️ npm install failed with code $NPM_EXIT. Trying npm ci..."
            npm ci --omit=dev 2>&1 | tee -a /tmp/npm_install.log
            NPM_EXIT=$?
            if [ $NPM_EXIT -ne 0 ]; then
                echo "❌ Failed to install Node dependencies. Check /tmp/npm_install.log"
                echo "Continuing anyway - modules may be pre-installed..."
            fi
        fi
    else
        echo "✅ Node modules already installed"
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
    
    # Wait for Baileys to be ready (with timeout)
    echo "⏳ Waiting for Baileys to start (max 15s)..."
    BAILEYS_READY=false
    for i in {1..15}; do
        sleep 1
        if curl -sf http://127.0.0.1:${BAILEYS_PORT}/healthz > /dev/null 2>&1; then
            echo "✅ Baileys is ready! (PID: $BAI, 127.0.0.1:${BAILEYS_PORT})"
            BAILEYS_READY=true
            break
        fi
        echo -n "."
    done
    echo ""
    
    # Show Baileys logs if it failed to start
    if [ "$BAILEYS_READY" = "false" ]; then
        echo "⚠️ Baileys may not be responding. Last 30 lines of logs:"
        tail -30 /tmp/baileys_prod.log 2>/dev/null || echo "No logs available yet"
        echo ""
        echo "🔍 Checking if process is still running..."
        if kill -0 $BAI 2>/dev/null; then
            echo "✅ Baileys process is running (PID: $BAI) - may just be slow to start"
        else
            echo "❌ Baileys process died immediately - check /tmp/baileys_prod.log"
            echo "Showing full log:"
            cat /tmp/baileys_prod.log 2>/dev/null || echo "No logs available"
        fi
    fi
else
    echo "⏭️ Skipping Baileys - using external service"
    BAI=0  # Dummy PID
fi

# 2) Start Flask/ASGI with Uvicorn on EXTERNAL port (native WebSocket support - BUILD 119.5)
echo "🟡 Starting BUILD 119.5 with Uvicorn ASGI on EXTERNAL port 0.0.0.0:${PORT}..."
# ⚡ BUILD 119.5: Single worker, no reload, stable production config
exec uvicorn asgi:app \
  --host 0.0.0.0 --port ${PORT} \
  --ws websockets --lifespan off \
  --workers 1 --timeout-keep-alive 75 \
  --no-server-header --log-level info

echo "🎯 Both services running. System ready!"
echo "📊 EXTERNAL Access: Port ${PORT} (exposed)"
echo "📊 INTERNAL Baileys: 127.0.0.1:${BAILEYS_PORT} (not exposed)"
echo "📝 Logs: /tmp/baileys_prod.log"

# Give services time to fully start up before announcing ready
sleep 5
echo "🔍 Final status check..."

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

# ⚡ BUILD 119.5: No auto-restart loop - exec handles process lifecycle
# The 'exec' above replaces this script with uvicorn process
# Uvicorn will run until manually stopped or killed