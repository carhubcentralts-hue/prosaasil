#!/usr/bin/env bash
# Start both Flask and Baileys for development

echo "🚀 Starting development services..."

# 1. Start Baileys in background
echo "📱 Starting Baileys WhatsApp Service on port 3300..."
cd services/baileys && nohup node server.js > /tmp/baileys.log 2>&1 &
BAILEYS_PID=$!
cd ../..
echo "✅ Baileys started (PID: $BAILEYS_PID)"

# 2. Start Flask (will block here)
echo "🐍 Starting Flask application..."
python3 server/app.py
