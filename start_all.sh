#!/bin/bash
set -euo pipefail

# ---- נעילת ריצה למניעת כפילויות ----
LOCK="/tmp/agentlocator.lock"
if [[ -f "$LOCK" ]]; then
  echo "⚠️ LOCK exists; killing previous pids..."
  pkill -9 -f "gunicorn|main:app" || true
  pkill -9 -f "node .*baileys" || true
  rm -f "$LOCK"
fi
touch "$LOCK"

# ---- ENV יציב ----
export PUBLIC_BASE_URL="${PUBLIC_BASE_URL%/}"
export PORT="${PORT:-5000}"

# מצב ברירת מחדל: AI (אפשר לעקוף מבחוץ)
export WS_MODE="${WS_MODE:-AI}"
export HEBREW_REALTIME_ENABLED="${HEBREW_REALTIME_ENABLED:-true}"

echo "🔧 ENV:"
echo "PUBLIC_BASE_URL=$PUBLIC_BASE_URL"
echo "PORT=$PORT"
echo "WS_MODE=$WS_MODE"
echo "HEBREW_REALTIME_ENABLED=$HEBREW_REALTIME_ENABLED"

# ---- הרמת Baileys (אם קיים) ----
NODE_PID=""
if [[ -d "baileys-bridge" ]]; then
  echo "🚀 starting Baileys bridge..."
  ( cd baileys-bridge && npm ci --omit=dev && node index.js ) &
  NODE_PID=$!
  echo "Baileys PID=$NODE_PID"
fi

# ---- Flask+WS עם Eventlet ----
echo "🚀 starting gunicorn (eventlet)…"
python3 -m gunicorn -k eventlet -w 1 -b 0.0.0.0:${PORT} main:app &
GUNI_PID=$!
echo "Gunicorn PID=$GUNI_PID"

# ---- טרפ לסגירה מסודרת ----
cleanup() {
  echo "🧹 cleanup..."
  [[ -n "${GUNI_PID:-}" ]] && kill "$GUNI_PID" 2>/dev/null || true
  [[ -n "${NODE_PID:-}" ]] && kill "$NODE_PID" 2>/dev/null || true
  rm -f "$LOCK" || true
}
trap cleanup EXIT

# ---- המתנה; אם אחד נופל – ניקוי ----
wait -n || true
cleanup