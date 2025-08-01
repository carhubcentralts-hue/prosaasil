#!/bin/bash

echo "🚀 Starting Baileys WhatsApp Service..."

# Create auth directory if it doesn't exist
mkdir -p baileys_auth_info

# Start Baileys in background
nohup node baileys_client.js > baileys.log 2>&1 &

# Get the process ID
BAILEYS_PID=$!

echo "📱 Baileys started with PID: $BAILEYS_PID"
echo $BAILEYS_PID > baileys.pid

# Show initial output
sleep 3
echo "📋 Recent log output:"
tail -n 10 baileys.log

echo "✅ Baileys service is now running in background"
echo "📄 Logs: tail -f baileys.log"
echo "🛑 Stop: kill \$(cat baileys.pid)"