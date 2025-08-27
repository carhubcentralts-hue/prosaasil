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

# 🎯 Advanced Human-Like Conversation Configuration
export BARGE_IN="${BARGE_IN:-true}"          # מאפשר הפרעה לבוט כשאדם מדבר
export MIN_UTT_SEC="${MIN_UTT_SEC:-0.55}"    # שקט לסוף-מבע (הואץ ל-0.55s)
export MAX_UTT_SEC="${MAX_UTT_SEC:-6.0}"     # חיתוך בטיחות למבע ארוך
export VAD_RMS="${VAD_RMS:-210}"             # סף דיבור רגיש מעט
export VAD_HANGOVER_MS="${VAD_HANGOVER_MS:-180}"  # Hangover אחרי שקט
export RESP_MIN_DELAY_MS="${RESP_MIN_DELAY_MS:-280}" # "נשימה" לפני דיבור
export RESP_MAX_DELAY_MS="${RESP_MAX_DELAY_MS:-420}"
export REPLY_REFRACTORY_MS="${REPLY_REFRACTORY_MS:-850}" # קירור אחרי דיבור
export BARGE_IN_VOICE_FRAMES="${BARGE_IN_VOICE_FRAMES:-4}" # כמה פריימים כדי לעצור
export AI_GREETING_HE="${AI_GREETING_HE:-"שלום! איך אפשר לעזור?"}"
export TWIML_PLAY_GREETING="${TWIML_PLAY_GREETING:-false}"  # שלא תהיה ברכה <Play> לפני Connect

echo "🔧 ENV:"
echo "PUBLIC_BASE_URL=$PUBLIC_BASE_URL"
echo "PORT=$PORT"
echo "WS_MODE=$WS_MODE"
echo "HEBREW_REALTIME_ENABLED=$HEBREW_REALTIME_ENABLED"
echo "🎯 HUMAN-LIKE CONVERSATION:"
echo "   BARGE_IN=$BARGE_IN, MIN_UTT=$MIN_UTT_SEC, MAX_UTT=$MAX_UTT_SEC, VAD_RMS=$VAD_RMS"
echo "   HANGOVER=${VAD_HANGOVER_MS}ms, BREATH=${RESP_MIN_DELAY_MS}-${RESP_MAX_DELAY_MS}ms" 
echo "   REFRACTORY=${REPLY_REFRACTORY_MS}ms, BARGE_FRAMES=$BARGE_IN_VOICE_FRAMES"

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