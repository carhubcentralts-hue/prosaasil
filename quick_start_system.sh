#!/bin/bash
set -e

echo "🚀 Starting System with Supervisor Pattern..."

# Environment setup
export PORT=5000
export BAILEYS_PORT=3310
export WHATSAPP_PROVIDER=baileys
export BAILEYS_WEBHOOK_SECRET=${BAILEYS_WEBHOOK_SECRET:-"internal-secret"}
export PUBLIC_BASE_URL=${PUBLIC_BASE_URL:-"http://127.0.0.1:5000"}

echo "📦 Installing Baileys dependencies..."
cd services/baileys
npm install &> /dev/null || echo "Dependencies installation warning ignored"
cd ../..

echo "📱 Starting Baileys WhatsApp service..."
cd services/baileys
nohup node server.js > ../../baileys_service.log 2>&1 &
BAILEYS_PID=$!
echo "Baileys PID: $BAILEYS_PID"
echo $BAILEYS_PID > ../../baileys.pid
cd ../..

sleep 2

echo "🐍 Starting Flask server..."
nohup python -m gunicorn wsgi:app -k eventlet -w 1 -b 0.0.0.0:5000 \
  --worker-connections 256 --timeout 120 --keep-alive 75 \
  --log-level info --access-logfile flask_access.log --error-logfile flask_error.log > flask_service.log 2>&1 &
FLASK_PID=$!
echo "Flask PID: $FLASK_PID"
echo $FLASK_PID > flask.pid

echo "✅ Both services started!"
echo "Baileys PID: $BAILEYS_PID (port 3310)"
echo "Flask PID: $FLASK_PID (port 5000)"

# Monitor and keep alive
for i in {1..120}; do
    sleep 2
    if ! kill -0 $BAILEYS_PID 2>/dev/null; then
        echo "❌ Baileys died, restarting..."
        cd services/baileys
        nohup node server.js > ../../baileys_service.log 2>&1 &
        BAILEYS_PID=$!
        echo $BAILEYS_PID > ../../baileys.pid
        cd ../..
    fi
    
    if ! kill -0 $FLASK_PID 2>/dev/null; then
        echo "❌ Flask died, restarting..."
        nohup python -m gunicorn wsgi:app -k eventlet -w 1 -b 0.0.0.0:5000 \
          --worker-connections 256 --timeout 120 --keep-alive 75 \
          --log-level info --access-logfile flask_access.log --error-logfile flask_error.log > flask_service.log 2>&1 &
        FLASK_PID=$!
        echo $FLASK_PID > flask.pid
    fi
    
    if [ $((i % 30)) -eq 0 ]; then
        echo "💓 Supervisor heartbeat: Baileys($BAILEYS_PID) Flask($FLASK_PID) - $i/120"
    fi
done

echo "🏁 Supervisor finished after 4 minutes"