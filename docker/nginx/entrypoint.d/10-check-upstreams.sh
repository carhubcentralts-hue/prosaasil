#!/bin/sh
# ===========================================
# Upstream Health Check Script for NGINX
# ===========================================
# This script verifies that all required upstream services are reachable
# before starting NGINX. This prevents the 502 Bad Gateway error when
# upstream services are not available.
#
# IMPORTANT: This runs at container startup, not at build time.
# ===========================================

set -e

echo "[NGINX] Checking upstream services..."

# Hardcoded upstreams (matching the nginx config)
API_UPSTREAM="prosaas-api:5000"
CALLS_UPSTREAM="prosaas-calls:5050"

echo "[NGINX] Expected upstreams:"
echo "  API: ${API_UPSTREAM}"
echo "  CALLS: ${CALLS_UPSTREAM}"

# Check API upstream
echo "[NGINX] Checking API upstream: ${API_UPSTREAM}"
MAX_RETRIES=30
RETRY=0
while [ $RETRY -lt $MAX_RETRIES ]; do
  if wget -qO- --timeout=2 "http://${API_UPSTREAM}/health" >/dev/null 2>&1; then
    echo "[NGINX] ✅ API upstream is reachable"
    break
  fi
  RETRY=$((RETRY + 1))
  if [ $RETRY -lt $MAX_RETRIES ]; then
    echo "[NGINX] API upstream not ready yet, retrying in 2s... (${RETRY}/${MAX_RETRIES})"
    sleep 2
  else
    echo "[NGINX] ❌ ERROR: API upstream (${API_UPSTREAM}) is NOT reachable after ${MAX_RETRIES} attempts"
    echo "[NGINX] This will cause 502 Bad Gateway errors on /api/ endpoints"
    exit 1
  fi
done

# Check CALLS upstream
echo "[NGINX] Checking CALLS upstream: ${CALLS_UPSTREAM}"
RETRY=0
while [ $RETRY -lt $MAX_RETRIES ]; do
  if wget -qO- --timeout=2 "http://${CALLS_UPSTREAM}/health" >/dev/null 2>&1; then
    echo "[NGINX] ✅ CALLS upstream is reachable"
    break
  fi
  RETRY=$((RETRY + 1))
  if [ $RETRY -lt $MAX_RETRIES ]; then
    echo "[NGINX] CALLS upstream not ready yet, retrying in 2s... (${RETRY}/${MAX_RETRIES})"
    sleep 2
  else
    echo "[NGINX] ❌ ERROR: CALLS upstream (${CALLS_UPSTREAM}) is NOT reachable after ${MAX_RETRIES} attempts"
    echo "[NGINX] This will cause 502 Bad Gateway errors on /ws/ and /webhook endpoints"
    exit 1
  fi
done

echo "[NGINX] ✅ All upstream services are healthy"
