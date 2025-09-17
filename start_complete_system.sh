#!/bin/bash
set -e

echo "🚀 Starting AgentLocator Complete System..."

# Install Baileys dependencies
echo "📦 Installing Baileys dependencies..."
cd services/baileys
npm install 2>/dev/null || true

# Start Baileys service in background
echo "📱 Starting Baileys WhatsApp service..."
BAILEYS_WEBHOOK_SECRET=$BAILEYS_WEBHOOK_SECRET \
PUBLIC_BASE_URL=$PUBLIC_BASE_URL \
BAILEYS_PORT=${BAILEYS_PORT:-3310} \
node server.js >> baileys.log 2>&1 &

echo "📱 Baileys PID: $!"
echo $! > ../baileys.pid

# Return to main directory (repo root)
cd ../..

# Start Python Flask server with Gunicorn in foreground
echo "🐍 Starting Flask server with Gunicorn..."
exec env EVENTLET_NO_GREENDNS=1 EVENTLET_HUB=poll \
gunicorn wsgi:app -k eventlet -w 1 -b 0.0.0.0:${PORT} \
  --worker-connections 256 --timeout 120 --keep-alive 75 \
  --log-level info --access-logfile - --error-logfile -