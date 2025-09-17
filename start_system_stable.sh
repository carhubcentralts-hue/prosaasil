#!/bin/bash
# הפעלה יציבה של המערכת לפי ההנחיות המדויקות
set -e

echo "🚀 Starting AgentLocator System - 2 ports only"
echo "📊 Ports: Flask:5000 + Baileys:3300"

# וודא ENV variables
export BAILEYS_PORT=3300
export FLASK_BASE_URL="http://127.0.0.1:5000"
export BAILEYS_BASE_URL="http://127.0.0.1:3300"

echo "🔧 ENV: BAILEYS_PORT=$BAILEYS_PORT"
echo "🔧 ENV: BAILEYS_BASE_URL=$BAILEYS_BASE_URL"
echo "🔧 ENV: FLASK_BASE_URL=$FLASK_BASE_URL"
echo "🔧 ENV: INTERNAL_SECRET=$([ -n "$INTERNAL_SECRET" ] && echo 'SET' || echo 'MISSING')"

# נקה תהליכים ישנים
pkill -f "node.*server" 2>/dev/null || true
pkill -f gunicorn 2>/dev/null || true
sleep 2

# הפעל Baileys בbackground
echo "🟡 Starting Baileys on port 3300..."
cd services/whatsapp
nohup node baileys_service.js > /tmp/baileys_system.log 2>&1 &
BAILEYS_PID=$!
echo "✅ Baileys started (PID: $BAILEYS_PID)"
cd ../..

# המתן לBaileys להתחיל
sleep 3

# בדוק Baileys
if curl -s http://127.0.0.1:3300/healthz >/dev/null 2>&1; then
    echo "✅ Baileys responsive on 3300"
else
    echo "❌ Baileys not responding on 3300"
    exit 1
fi

# הפעל Flask עם gunicorn בforeground (כך המערכת נשארת חיה)
echo "🟡 Starting Flask on port 5000 (foreground)..."
exec gunicorn wsgi:app -k eventlet -w 1 -b 0.0.0.0:5000 --timeout 60 --keep-alive 30 --log-level info --access-logfile - --error-logfile -