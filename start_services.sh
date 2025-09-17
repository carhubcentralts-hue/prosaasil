#!/bin/bash
# Comprehensive startup script for Flask + Baileys services
# Sets up environment and starts services persistently

echo "🚀 Starting AgentLocator Services..."

# Set required environment variables
export PYTHONUNBUFFERED=1
export PYTHONPATH=.
export PORT=5000
export FLASK_ENV=production
export INTERNAL_SECRET=test-local-secret-123
export FLASK_BASE_URL=http://localhost:5000
export BAILEYS_PORT=3001
export BAILEYS_BASE_URL=http://localhost:3001

# Kill any existing services on ports 5000 and 3001
echo "🧹 Cleaning up existing services..."
lsof -ti:5000 | xargs -r kill -9 2>/dev/null || true
lsof -ti:3001 | xargs -r kill -9 2>/dev/null || true
sleep 2

# Start Flask service
echo "🌐 Starting Flask app on port 5000..."
python run_production_server.py > flask.log 2>&1 &
FLASK_PID=$!
echo $FLASK_PID > flask.pid
echo "✅ Flask started with PID: $FLASK_PID"

# Wait for Flask to start
echo "⏳ Waiting for Flask to initialize..."
sleep 5

# Check if Flask is running
if ! curl -s http://localhost:5000/healthz > /dev/null 2>&1; then
    echo "❌ Flask failed to start properly"
    cat flask.log
    exit 1
fi
echo "✅ Flask is running and healthy"

# Start Baileys multi-tenant service  
echo "📱 Starting Baileys multi-tenant service on port 3001..."
cd services/whatsapp
node baileys_service.js > ../../baileys.log 2>&1 &
BAILEYS_PID=$!
echo $BAILEYS_PID > ../../baileys.pid
cd ../..
echo "✅ Baileys started with PID: $BAILEYS_PID"

# Wait for Baileys to start
echo "⏳ Waiting for Baileys to initialize..."
sleep 3

# Check if Baileys is running
if ! curl -s -H "X-Internal-Secret: test-local-secret-123" http://localhost:3001/healthz > /dev/null 2>&1; then
    echo "⚠️ Baileys might be starting up, checking logs..."
    tail -n 10 baileys.log
fi

echo ""
echo "📋 Service Status Summary:"
echo "- Flask:   http://localhost:5000  (PID: $FLASK_PID)"
echo "- Baileys: http://localhost:3001  (PID: $BAILEYS_PID)"
echo ""
echo "🔍 Health Check URLs:"
echo "- /healthz:  curl http://localhost:5000/healthz"
echo "- /version:  curl http://localhost:5000/version"  
echo "- /readyz:   curl http://localhost:5000/readyz"
echo ""
echo "📊 Logs:"
echo "- Flask:   tail -f flask.log"
echo "- Baileys: tail -f baileys.log"
echo ""
echo "🛑 To stop services: ./stop_services.sh"
echo "✅ Services startup complete!"