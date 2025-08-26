#!/usr/bin/env bash
set -euo pipefail

# Ensure correct working directory - fix for Replit
echo "🔧 Current directory: $(pwd)"
echo "🚀 Starting from: $(dirname "$0")"

echo "🚀 Starting AgentLocator 76 - Complete System with Baileys"

# Create necessary directories  
mkdir -p baileys-bridge/auth
mkdir -p static/tts
mkdir -p logs

# Set environment defaults
export PORT=${PORT:-5000}
export BAILEYS_PORT=${BAILEYS_PORT:-4001}

# === WebSocket mode: SINK | ECHO | AI ===
export WS_MODE=${WS_MODE:-ECHO}
export BAILEYS_WEBHOOK=${BAILEYS_WEBHOOK:-http://127.0.0.1:5000/webhook/whatsapp/baileys}
export BAILEYS_SECRET=${BAILEYS_SECRET:-default-baileys-secret}
export WA_BAILEYS_PORT=${WA_BAILEYS_PORT:-4001}  # Legacy support
export WA_SESSION_DIR=${WA_SESSION_DIR:-./baileys-bridge/auth}
export PYTHON_WEBHOOK_URL=${PYTHON_WEBHOOK_URL:-$BAILEYS_WEBHOOK}
export WA_SHARED_SECRET=${WA_SHARED_SECRET:-$BAILEYS_SECRET}

# Install Baileys dependencies if needed
if [ -d "baileys-bridge" ] && [ ! -d "baileys-bridge/node_modules" ]; then
    echo "📦 Installing Baileys dependencies..."
    cd baileys-bridge && npm ci --omit=dev && cd ..
else
    echo "⚠️ Baileys bridge directory not found or already installed"
fi

# Set up GCP credentials if provided
if [ -n "${GCP_CREDENTIALS_JSON:-}" ]; then
    echo "🔧 Setting up GCP credentials..."
    echo "$GCP_CREDENTIALS_JSON" > /tmp/gcp-credentials.json
    export GOOGLE_APPLICATION_CREDENTIALS=/tmp/gcp-credentials.json
fi

# Start Baileys bridge if enabled
if [ "${ENABLE_WA_BAILEYS:-true}" = "true" ] && [ -d "baileys-bridge" ]; then
    echo "🟢 Starting Baileys bridge on port $BAILEYS_PORT..."
    cd baileys-bridge
    node index.js &
    BAILEYS_PID=$!
    cd ..
    
    # Give bridge time to start
    sleep 3
    echo "✅ Baileys bridge started (PID: $BAILEYS_PID)"
else
    echo "⚪ Baileys bridge disabled or directory not found"
fi

echo "🚀 Starting Flask API with Eventlet (WebSocket support)..."
echo "⚡ Environment: NODE_ENV=${NODE_ENV:-development}, PORT=$PORT"

# Start main application with Eventlet for WebSocket support
exec python3 -m gunicorn \
    -k eventlet \
    -w 1 \
    --bind 0.0.0.0:$PORT \
    --access-logfile - \
    --error-logfile - \
    --timeout 60 \
    --graceful-timeout 30 \
    main:app