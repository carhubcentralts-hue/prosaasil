#!/bin/bash
# הפעלה יציבה של המערכת לפי ההנחיות המדויקות
set -e

echo "🚀 Starting AgentLocator System - תוכנית מושלמת"
echo "📊 Ports: Frontend:3310 + Flask:5000 + Baileys:3300"

# וודא ENV variables - תוכנית מושלמת
export BAILEYS_PORT=3300
export FLASK_BASE_URL="http://127.0.0.1:5000"
export BAILEYS_BASE_URL="http://127.0.0.1:3300"
export FRONTEND_PORT=3310

echo "🔧 ENV: BAILEYS_PORT=$BAILEYS_PORT"
echo "🔧 ENV: BAILEYS_BASE_URL=$BAILEYS_BASE_URL"
echo "🔧 ENV: FLASK_BASE_URL=$FLASK_BASE_URL"
echo "🔧 ENV: INTERNAL_SECRET=$([ -n "$INTERNAL_SECRET" ] && echo 'SET' || echo 'MISSING')"

# נקה תהליכים ישנים בצורה מדויקת
pkill -9 -f "services/whatsapp/baileys_service.js" 2>/dev/null || true
pkill -9 -f "gunicorn" 2>/dev/null || true
pkill -9 -f "npm run dev" 2>/dev/null || true

# בדיקת INTERNAL_SECRET מראש
if [ -z "$INTERNAL_SECRET" ]; then
  echo "❌ INTERNAL_SECRET missing!"
  exit 1
fi

# בדיקת ports פנויים - fail fast אם תפוסים
if lsof -i :5000 2>/dev/null; then echo "❌ Port 5000 תפוס!"; exit 1; fi
if lsof -i :3300 2>/dev/null; then echo "❌ Port 3300 תפוס!"; exit 1; fi
if lsof -i :3310 2>/dev/null; then echo "❌ Port 3310 תפוס!"; exit 1; fi

sleep 2

# הפעל Baileys בbackground
echo "🟡 Starting Baileys on port 3300..."
cd services/whatsapp
nohup node baileys_service.js > /tmp/baileys_system.log 2>&1 &
BAILEYS_PID=$!
echo "✅ Baileys started (PID: $BAILEYS_PID)"

# Signal trap לניקוי התהליכים
trap 'kill ${BAILEYS_PID} ${FLASK_PID} ${VITE_PID} 2>/dev/null || true' TERM INT EXIT

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

# הפעל Flask בbackground
echo "🟡 Starting Flask on port 5000..."
gunicorn wsgi:app -k eventlet -w 1 -b 0.0.0.0:5000 --timeout 60 --keep-alive 30 --log-level info --access-logfile - --error-logfile - &
FLASK_PID=$!
echo "✅ Flask started (PID: $FLASK_PID)"

# בדוק Flask health
echo "🔍 בדיקת Flask..."
for i in {1..10}; do
  if curl -s http://127.0.0.1:5000/healthz >/dev/null 2>&1; then
    echo "✅ Flask פעיל על 5000!"
    break
  fi
  if [ $i -eq 10 ]; then
    echo "❌ Flask נכשל!"
    exit 1
  fi
  sleep 1
done

# עכשיו הפעל Vite frontend על 3310 עם trap support
echo "🌐 Starting Vite Frontend on port 3310..."
npm run dev &
VITE_PID=$!
echo "✅ Vite started (PID: $VITE_PID)"

# המתן ל-Vite (foreground)
echo "🎯 כל השירותים פעילים! המערכת מוכנה."
echo "📊 Frontend: http://localhost:3310"
echo "📊 Flask API: http://localhost:5000"
echo "📊 Baileys: http://localhost:3300 (internal)"
wait ${VITE_PID}