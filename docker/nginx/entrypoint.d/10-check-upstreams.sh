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

# Extract upstream hostnames from nginx config
# Note: These are hardcoded at build time via envsubst
API_UPSTREAM=$(grep -oP 'proxy_pass http://\K[^/;]+' /etc/nginx/conf.d/prosaas.conf | grep -E 'prosaas-api|backend' | head -1 || echo "")
CALLS_UPSTREAM=$(grep -oP 'proxy_pass http://\K[^/;]+' /etc/nginx/conf.d/prosaas.conf | grep -E 'prosaas-calls|backend' | head -1 || echo "")

echo "[NGINX] Found upstreams:"
echo "  API: ${API_UPSTREAM}"
echo "  CALLS: ${CALLS_UPSTREAM}"

# Check API upstream
if [ -n "$API_UPSTREAM" ]; then
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
fi

# Check CALLS upstream (only if different from API)
if [ -n "$CALLS_UPSTREAM" ] && [ "$CALLS_UPSTREAM" != "$API_UPSTREAM" ]; then
  echo "[NGINX] Checking CALLS upstream: ${CALLS_UPSTREAM}"
  MAX_RETRIES=30
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
fi

echo "[NGINX] ✅ All upstream services are healthy"
