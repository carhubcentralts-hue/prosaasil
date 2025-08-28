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

# 🎯 Optimized Human-Like Conversation Configuration
# סיום מבע (VAD) — מהיר אבל לא מקוטע
export MIN_UTT_SEC="${MIN_UTT_SEC:-0.48}"        # שקט לסיום
export VAD_HANGOVER_MS="${VAD_HANGOVER_MS:-130}" # אינרציה קצרה אחרי שקט
export MAX_UTT_SEC="${MAX_UTT_SEC:-7.0}"
export VAD_RMS="${VAD_RMS:-150}"                 # סף קול רגיש מאוד (לא צריך לצעוק!)

# קצב "אנושי"
export RESP_MIN_DELAY_MS="${RESP_MIN_DELAY_MS:-200}"   # נשימה קצרה לפני דיבור
export RESP_MAX_DELAY_MS="${RESP_MAX_DELAY_MS:-320}"
export REPLY_REFRACTORY_MS="${REPLY_REFRACTORY_MS:-700}" # קירור אחרי דיבור הבוט

# Barge-in (עצור כשאדם מדבר מעליך)
export BARGE_IN="${BARGE_IN:-true}"
export BARGE_IN_VOICE_FRAMES="${BARGE_IN_VOICE_FRAMES:-3}"

# "סימן חיים" אם LLM מתעכב
export THINKING_HINT_MS="${THINKING_HINT_MS:-700}"
export THINKING_TEXT_HE="${THINKING_TEXT_HE:-"שנייה… בודקת"}"

# ברכה: דרך TTS אחרי start (אל תשתמש ב-<Play>)
export TWIML_PLAY_GREETING="${TWIML_PLAY_GREETING:-false}"
export AI_GREETING_HE="${AI_GREETING_HE:-"היי, אני כאן — איך אפשר לעזור?"}"

# אורך תשובות
export LLM_TARGET_STYLE="${LLM_TARGET_STYLE:-warm_helpful}"
export LLM_MIN_CHARS="${LLM_MIN_CHARS:-140}"    # מינימום ~2 משפטים
export LLM_MAX_CHARS="${LLM_MAX_CHARS:-420}"    # מקסימום קצר בטלפון

echo "🔧 ENV:"
echo "PUBLIC_BASE_URL=$PUBLIC_BASE_URL"
echo "PORT=$PORT"
echo "WS_MODE=$WS_MODE"
echo "HEBREW_REALTIME_ENABLED=$HEBREW_REALTIME_ENABLED"
echo "🎯 OPTIMIZED HUMAN-LIKE CONVERSATION:"
echo "   BARGE_IN=$BARGE_IN, MIN_UTT=$MIN_UTT_SEC, MAX_UTT=$MAX_UTT_SEC, VAD_RMS=$VAD_RMS"
echo "   HANGOVER=${VAD_HANGOVER_MS}ms, BREATH=${RESP_MIN_DELAY_MS}-${RESP_MAX_DELAY_MS}ms" 
echo "   REFRACTORY=${REPLY_REFRACTORY_MS}ms, BARGE_FRAMES=$BARGE_IN_VOICE_FRAMES"
echo "   LLM: ${LLM_TARGET_STYLE}, ${LLM_MIN_CHARS}-${LLM_MAX_CHARS} chars"
echo "   THINKING: ${THINKING_HINT_MS}ms → '${THINKING_TEXT_HE}'"

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