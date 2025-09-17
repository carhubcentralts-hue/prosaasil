#!/usr/bin/env bash
set -euo pipefail
export PYTHONUNBUFFERED=1
export BAILEYS_PORT="${BAILEYS_PORT:-3300}"
export FLASK_BASE_URL="${FLASK_BASE_URL:-http://127.0.0.1:5000}"
export INTERNAL_SECRET="${INTERNAL_SECRET:?missing}"

mkdir -p logs

# מרימים את Baileys בחזית משנה, עם לוג לקובץ וקונסול
stdbuf -oL -eL node --trace-uncaught --unhandled-rejections=strict services/baileys/server.js \
  2>&1 | tee -a logs/baileys.log & BAI=$!

# מרימים את Flask (בחר אחד מהשניים)
# python -u main.py 2>&1 | tee -a logs/flask.log & FL=$!
gunicorn -w 1 -k eventlet -b 0.0.0.0:5000 wsgi:app 2>&1 | tee -a logs/flask.log & FL=$!

trap 'echo "[TRAP] stopping..."; kill -TERM $BAI $FL 2>/dev/null || true; wait || true' INT TERM

# נמתין, ואם אחד נופל – נדפיס קוד יציאה ונסגור את השני כדי שיהיה ברור שיש תקלה
while true; do
  if ! kill -0 $BAI 2>/dev/null; then
    echo "[EXIT] Baileys exited ($BAI)"; break
  fi
  if ! kill -0 $FL 2>/dev/null; then
    echo "[EXIT] Flask exited ($FL)"; break
  fi
  sleep 1
done
kill -TERM $BAI $FL 2>/dev/null || true
wait || true