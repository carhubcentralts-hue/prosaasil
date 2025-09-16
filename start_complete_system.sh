#!/bin/bash
set -e

echo "🚀 Starting AgentLocator Complete System..."

# Install Baileys dependencies
echo "📦 Installing Baileys dependencies..."
cd baileys-service
npm ci

# Start Baileys service in background
echo "📱 Starting Baileys WhatsApp service..."
BAILEYS_WEBHOOK_SECRET=$BAILEYS_WEBHOOK_SECRET \
PUBLIC_BASE_URL=$PUBLIC_BASE_URL \
PORT=3001 \
node server.js >> baileys.log 2>&1 &

echo "📱 Baileys PID: $!"
echo $! > ../baileys.pid

# Return to main directory
cd ..

# Start Python Flask server with Gunicorn in foreground
echo "🐍 Starting Flask server with Gunicorn..."
exec env EVENTLET_NO_GREENDNS=1 EVENTLET_HUB=poll \
gunicorn wsgi:app -k eventlet -w 1 -b 0.0.0.0:${PORT} \
  --worker-connections 256 --timeout 120 --keep-alive 75 \
  --log-level info --access-logfile - --error-logfile -