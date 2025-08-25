#!/usr/bin/env bash
set -euo pipefail

echo "🚀 Starting AgentLocator 72 - Full Stack Deployment"

# Create necessary directories
mkdir -p baileys-bridge/session
mkdir -p server/static/voice_responses
mkdir -p logs

# Install dependencies
echo "📦 Installing Python dependencies..."
pip install --no-cache-dir -r requirements.txt

echo "📦 Installing Node.js dependencies..."
cd baileys-bridge && npm ci && cd ..

# Set environment defaults
export WA_BAILEYS_PORT=${WA_BAILEYS_PORT:-8000}
export WA_SESSION_DIR=${WA_SESSION_DIR:-./baileys-bridge/session}
export PYTHON_WEBHOOK_URL=${PYTHON_WEBHOOK_URL:-http://127.0.0.1:5000/webhook/whatsapp/baileys}

echo "🔧 Starting Baileys bridge on port $WA_BAILEYS_PORT..."
# Start bridge in background
node baileys-bridge/index.js &
BAILEYS_PID=$!

# Give bridge time to start
sleep 3

echo "🚀 Starting Flask API with Eventlet (WebSocket support)..."
# Start main application with Eventlet for WebSocket support
exec python3 -m gunicorn -k eventlet -w 1 -b 0.0.0.0:$PORT main:app