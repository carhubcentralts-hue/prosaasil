#!/usr/bin/env bash
set -euo pipefail
export PYTHONUNBUFFERED=1
export BAILEYS_PORT="${BAILEYS_PORT:-3300}"
export FLASK_BASE_URL="${FLASK_BASE_URL:-http://127.0.0.1:5000}"
export INTERNAL_SECRET="${INTERNAL_SECRET:?missing}"

node services/baileys/server.js & BAI=$!
gunicorn -w 1 -k eventlet -b 0.0.0.0:5000 wsgi:app & FL=$!

trap 'kill -TERM $BAI $FL 2>/dev/null || true; wait || true' INT TERM
# נשארים חיים כל עוד שני התהליכים חיים
while kill -0 $BAI 2>/dev/null && kill -0 $FL 2>/dev/null; do sleep 1; done