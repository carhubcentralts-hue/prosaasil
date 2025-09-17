#!/bin/bash
# Robust service starter for Flask and Baileys
set -e

echo "🚀 Starting AgentLocator Services"

# Clean up any existing processes
pkill -9 -f "services/baileys/server.js" 2>/dev/null || true
pkill -9 -f "gunicorn.*wsgi" 2>/dev/null || true
sleep 2

# Verify environment
if [ -z "$INTERNAL_SECRET" ]; then
    echo "❌ INTERNAL_SECRET not set"
    exit 1
fi

# Set environment variables
export BAILEYS_PORT=3300
export FLASK_BASE_URL="http://127.0.0.1:5000"
export BAILEYS_BASE_URL="http://127.0.0.1:3300"

echo "🔧 ENV: BAILEYS_PORT=$BAILEYS_PORT"
echo "🔧 ENV: INTERNAL_SECRET=$([ -n "$INTERNAL_SECRET" ] && echo 'SET' || echo 'MISSING')"

# Function to start Baileys service
start_baileys() {
    echo "🟡 Starting Baileys service on port 3300..."
    cd services/baileys
    nohup node server.js > /tmp/baileys.log 2>&1 &
    BAILEYS_PID=$!
    cd ../..
    echo "$BAILEYS_PID" > baileys.pid
    echo "✅ Baileys started (PID: $BAILEYS_PID)"
    
    # Wait and test
    sleep 3
    for i in {1..10}; do
        if curl -s http://127.0.0.1:3300/healthz >/dev/null 2>&1; then
            echo "✅ Baileys health check passed!"
            return 0
        fi
        sleep 1
    done
    echo "❌ Baileys health check failed!"
    return 1
}

# Function to start Flask service  
start_flask() {
    echo "🟡 Starting Flask service on port 5000..."
    nohup gunicorn wsgi:app -k eventlet -w 1 -b 0.0.0.0:5000 \
        --timeout 120 --keep-alive 30 --log-level error \
        --pid flask.pid --daemon > /tmp/flask.log 2>&1
    
    # Wait and test
    sleep 5
    for i in {1..15}; do
        if curl -s http://127.0.0.1:5000/healthz >/dev/null 2>&1; then
            echo "✅ Flask health check passed!"
            return 0
        fi
        sleep 1
    done
    echo "❌ Flask health check failed!"
    return 1
}

# Start services
start_baileys || exit 1
start_flask || exit 1

echo "🎯 All services started successfully!"
echo "📊 Baileys: http://localhost:3300 (PID: $(cat baileys.pid 2>/dev/null || echo 'unknown'))"
echo "📊 Flask: http://localhost:5000 (PID: $(cat flask.pid 2>/dev/null || echo 'unknown'))"

# Test key endpoints
echo -e "\n🔍 Testing endpoints:"
curl -s http://127.0.0.1:5000/healthz && echo " ← Flask health OK"
curl -s http://127.0.0.1:3300/healthz && echo " ← Baileys health OK"

echo -e "\n✅ Server startup completed successfully!"