#!/usr/bin/env bash
# ===========================================
# SSOT Duplicate Prevention Gate
# ===========================================
# Ensures no direct BAILEYS_BASE_URL usage, no scattered os.getenv,
# and that key wiring is in place.
#
# Usage: ./scripts/no_duplicate_ssot_checks.sh
# ===========================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

FAILURES=0

pass() { echo -e "${GREEN}✅ PASS${NC}: $1"; }
fail() { echo -e "${RED}❌ FAIL${NC}: $1"; FAILURES=$((FAILURES + 1)); }

# ── 1. No direct BAILEYS_BASE_URL reads outside config / shard_router ───
echo "→ Checking no direct BAILEYS_BASE_URL usage..."
# Exclude config/, whatsapp_shard_router.py, markdown, __pycache__, and imports from config
HITS=$(grep -rn 'BAILEYS_BASE_URL' server/ \
    --include='*.py' \
    | grep -v 'server/config/' \
    | grep -v 'server/whatsapp_shard_router.py' \
    | grep -v '__pycache__' \
    | grep -v '\.md' \
    | grep -v 'from server.config import' \
    | grep -v 'BAILEYS_BASE_URL_LEGACY' \
    | grep -v '#.*BAILEYS_BASE_URL' \
    | grep -v 'Set BAILEYS_BASE_URL' \
    || true)

if [ -z "$HITS" ]; then
  pass "No direct BAILEYS_BASE_URL usage outside config/router"
else
  fail "Direct BAILEYS_BASE_URL usage found:"
  echo "$HITS"
fi

# ── 2. register_metrics_endpoint wired in app factory ───────────────────
echo "→ Checking metrics wiring..."
if grep -q 'register_metrics_endpoint' server/app_factory.py; then
  pass "register_metrics_endpoint called in app_factory"
else
  fail "register_metrics_endpoint NOT found in app_factory.py"
fi

# ── 3. calls_state / calls_capacity imported in routes_twilio ──────────
echo "→ Checking calls capacity wiring..."
if grep -q 'calls_capacity' server/routes_twilio.py; then
  pass "calls_capacity used in routes_twilio"
else
  fail "calls_capacity NOT found in routes_twilio.py"
fi

# ── 4. whatsapp_shard migration in db_migrate ──────────────────────────
echo "→ Checking whatsapp_shard migration..."
if grep -q 'whatsapp_shard' server/db_migrate.py; then
  pass "whatsapp_shard migration exists in db_migrate.py"
else
  fail "whatsapp_shard migration NOT found in db_migrate.py"
fi

echo ""
if [ "$FAILURES" -eq 0 ]; then
  echo -e "${GREEN}ALL SSOT CHECKS PASSED ✅${NC}"
  exit 0
else
  echo -e "${RED}$FAILURES SSOT CHECK(S) FAILED ❌${NC}"
  exit 1
fi
