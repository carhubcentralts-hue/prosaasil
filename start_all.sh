#!/usr/bin/env bash
set -euo pipefail

# Ensure correct working directory
cd "$(dirname "$0")"

echo "🚀 Starting AgentLocator 76 - Complete System"

# Create necessary directories
mkdir -p baileys-bridge/session
mkdir -p static/tts
mkdir -p logs

# Set environment defaults
export PORT=${PORT:-5000}
export WA_BAILEYS_PORT=${WA_BAILEYS_PORT:-8000}
export WA_SESSION_DIR=${WA_SESSION_DIR:-./baileys-bridge/session}
export PYTHON_WEBHOOK_URL=${PYTHON_WEBHOOK_URL:-http://127.0.0.1:5000/webhook/whatsapp/baileys}
export WA_SHARED_SECRET=${WA_SHARED_SECRET:-default-secret-key}

# Install dependencies if needed
if [ ! -d "baileys-bridge/node_modules" ]; then
    echo "📦 Installing Node.js dependencies..."
    cd baileys-bridge && npm ci && cd ..
fi

# Set up GCP credentials if provided
if [ -n "${GCP_CREDENTIALS_JSON:-}" ]; then
    echo "🔧 Setting up GCP credentials..."
    echo "$GCP_CREDENTIALS_JSON" > /tmp/gcp-credentials.json
    export GOOGLE_APPLICATION_CREDENTIALS=/tmp/gcp-credentials.json
fi

# Check if Baileys should be enabled
if [ "${ENABLE_WA_BAILEYS:-true}" = "true" ]; then
    echo "🟢 Starting Baileys bridge on port $WA_BAILEYS_PORT..."
    cd baileys-bridge
    node index.js &
    BAILEYS_PID=$!
    cd ..
    
    # Give bridge time to start
    sleep 3
    echo "✅ Baileys bridge started (PID: $BAILEYS_PID)"
else
    echo "⚪ Baileys bridge disabled"
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
    AgentLocator.main:app