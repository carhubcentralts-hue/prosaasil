#!/bin/bash
set -e

echo "🚀 Starting PERMANENT Baileys Supervisor..."

# Environment setup
export PORT=5000
export BAILEYS_PORT=3310
export WHATSAPP_PROVIDER=baileys

cleanup() {
    echo "🛑 Supervisor cleanup..."
    if [ -f baileys.pid ]; then
        PID=$(cat baileys.pid)
        kill $PID 2>/dev/null || true
        rm -f baileys.pid
    fi
    exit 0
}

trap cleanup SIGINT SIGTERM EXIT

start_baileys() {
    echo "📱 Starting Baileys service..."
    cd services/baileys
    npm install &> /dev/null || true
    nohup node server.js > ../../baileys_service.log 2>&1 &
    BAILEYS_PID=$!
    echo $BAILEYS_PID > ../../baileys.pid
    cd ../..
    echo "✅ Baileys started with PID: $BAILEYS_PID"
}

# Start Baileys initially
start_baileys

# Infinite monitoring loop
COUNTER=0
while true; do
    sleep 5
    COUNTER=$((COUNTER + 1))
    
    if [ -f baileys.pid ]; then
        PID=$(cat baileys.pid)
        if ! kill -0 $PID 2>/dev/null; then
            echo "❌ Baileys died (PID $PID), restarting..."
            start_baileys
        fi
    else
        echo "❌ No PID file, restarting Baileys..."
        start_baileys
    fi
    
    # Health check
    if ! curl -s -m 2 http://127.0.0.1:3310/healthz > /dev/null; then
        echo "❌ Health check failed, restarting Baileys..."
        if [ -f baileys.pid ]; then
            PID=$(cat baileys.pid)
            kill $PID 2>/dev/null || true
        fi
        sleep 2
        start_baileys
    fi
    
    # Heartbeat every minute
    if [ $((COUNTER % 12)) -eq 0 ]; then
        PID=$(cat baileys.pid 2>/dev/null || echo "NO-PID")
        echo "💓 Supervisor alive: Baileys PID $PID - $(date)"
    fi
done