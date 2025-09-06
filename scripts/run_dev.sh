#!/usr/bin/env bash
set -euo pipefail
# Force a known port if $PORT is empty (workspace preview)
: "${PORT:=8000}"
export PORT
echo "[RUN] PORT=$PORT"
python wsgi.py