#!/usr/bin/env bash
set -euo pipefail

export PYTHONUNBUFFERED=1
export PORT="${PORT:-5000}"                   # לפלטפורמות שמצפות למשתנה PORT
export FLASK_BASE_URL="${FLASK_BASE_URL:-http://127.0.0.1:5000}"
export BAILEYS_PORT="${BAILEYS_PORT:-3300}"
# INTERNAL_SECRET צריך להיות מוגדר בסודות הדיפלוימנט

# 1) Start Baileys (תקן לנתיב הכניסה שלך)
node services/whatsapp/baileys_service.js &
BAI=$!

# 2) Start Flask (ה־listener היחיד החיצוני)
gunicorn -w 1 -k eventlet -b 0.0.0.0:${PORT} wsgi:app & 
FL=$!

# keep both alive and cleanly shutdown
trap 'kill -TERM $BAI $FL 2>/dev/null || true; wait || true' INT TERM
while kill -0 $BAI 2>/dev/null && kill -0 $FL 2>/dev/null; do sleep 1; done