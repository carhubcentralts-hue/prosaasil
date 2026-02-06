#!/usr/bin/env bash
# ===========================================
# Production Smoke Test
# ===========================================
# Validates that docker-compose production profiles work,
# services come up healthy, and key endpoints respond.
#
# Usage:
#   ./scripts/prod_smoke.sh              # Validate compose config only (no Docker needed)
#   ./scripts/prod_smoke.sh --full       # Full smoke: start services, hit endpoints, stop
#
# Exit code: 0 = all checks pass, non-zero = failure
# ===========================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

FAILURES=0
SKIPPED=0
MODE="${1:-config}"

pass() { echo -e "${GREEN}✅ PASS${NC}: $1"; }
fail() { echo -e "${RED}❌ FAIL${NC}: $1"; FAILURES=$((FAILURES + 1)); }
info() { echo -e "${YELLOW}ℹ️  INFO${NC}: $1"; }
skip() { echo -e "${YELLOW}⏭️  SKIP${NC}: $1"; SKIPPED=$((SKIPPED + 1)); }

# -------------------------------------------
# 1. Compose config validation (requires docker compose)
# -------------------------------------------
info "=== Compose Config Validation ==="

if ! command -v docker &> /dev/null; then
  skip "Docker not available — skipping compose config validation"
else

# Create temporary .env if missing (compose needs it)
TEMP_ENV=false
if [ ! -f .env ]; then
  touch .env
  TEMP_ENV=true
fi

echo "→ Base compose config..."
if docker compose -f docker-compose.yml config > /dev/null 2>&1; then
  pass "Base docker-compose.yml valid"
else
  fail "Base docker-compose.yml invalid"
fi

echo "→ Production compose config..."
if docker compose -f docker-compose.yml -f docker-compose.prod.yml config > /dev/null 2>&1; then
  pass "Production compose overlay valid"
else
  fail "Production compose overlay invalid"
fi

echo "→ Multi-worker profile..."
if docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile multi-worker config > /dev/null 2>&1; then
  pass "multi-worker profile valid"
else
  fail "multi-worker profile invalid"
fi

echo "→ Multi-shard profile..."
if docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile multi-shard config > /dev/null 2>&1; then
  pass "multi-shard profile valid"
else
  fail "multi-shard profile invalid"
fi

echo "→ Combined profiles..."
if docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile multi-worker --profile multi-shard config > /dev/null 2>&1; then
  pass "Combined multi-worker + multi-shard profiles valid"
else
  fail "Combined profiles invalid"
fi

# Clean up temporary .env
if [ "$TEMP_ENV" = true ]; then
  rm -f .env
fi

fi  # end docker check

# -------------------------------------------
# 2. Verify migration service ordering (file-based checks)
# -------------------------------------------
info "=== Migration Ordering Verification ==="

echo "→ Checking migrate service exists..."
if grep -q 'migrate:' docker-compose.yml 2>/dev/null; then
  pass "migrate service defined in docker-compose.yml"
else
  fail "migrate service NOT defined in docker-compose.yml"
fi

echo "→ Checking migrate command..."
if grep -q 'server.db_migrate' docker-compose.yml 2>/dev/null; then
  pass "migrate service runs server.db_migrate"
else
  fail "migrate service does NOT run server.db_migrate"
fi

echo "→ Checking API depends on migrate (prod)..."
if grep -A5 'prosaas-api' docker-compose.prod.yml 2>/dev/null | grep -q 'migrate'; then
  pass "prosaas-api depends on migrate in prod compose"
else
  # Check base compose too
  if grep -A10 'depends_on' docker-compose.yml 2>/dev/null | grep -q 'migrate'; then
    pass "Services depend on migrate in base compose"
  else
    fail "No service depends on migrate"
  fi
fi

# -------------------------------------------
# 3. Verify separate volumes for shards (file-based checks)
# -------------------------------------------
info "=== Shard Volume Isolation ==="

echo "→ Checking baileys shard 1 volume..."
if grep -q 'whatsapp_auth:' docker-compose.yml 2>/dev/null; then
  pass "baileys shard 1 has whatsapp_auth volume"
else
  fail "baileys shard 1 volume not found"
fi

echo "→ Checking baileys shard 2 volume..."
if grep -q 'whatsapp_auth_shard2' docker-compose.prod.yml 2>/dev/null; then
  pass "baileys shard 2 has whatsapp_auth_shard2 volume (separate)"
else
  fail "baileys shard 2 volume not found"
fi

# -------------------------------------------
# 4. SSOT wiring checks
# -------------------------------------------
info "=== SSOT Wiring Checks ==="

if bash scripts/no_duplicate_ssot_checks.sh 2>/dev/null; then
  pass "All SSOT duplicate checks"
else
  fail "SSOT duplicate checks"
fi

# -------------------------------------------
# 5. Full smoke test (only with --full flag)
# -------------------------------------------
if [ "$MODE" = "--full" ]; then
  info "=== Full Production Smoke Test ==="
  API_URL="${SMOKE_API_URL:-http://localhost:5000}"
  info "API URL: $API_URL"
  info "Starting services with combined profiles..."

  docker compose -f docker-compose.yml -f docker-compose.prod.yml \
    --profile multi-worker --profile multi-shard up -d 2>&1 || {
    fail "Failed to start services"
  }

  info "Waiting for services to become healthy (max 120s)..."
  TIMEOUT=120
  ELAPSED=0

  while [ $ELAPSED -lt $TIMEOUT ]; do
    if curl -sf "$API_URL/health" > /dev/null 2>&1; then
      pass "API /health endpoint responds"
      break
    fi
    sleep 5
    ELAPSED=$((ELAPSED + 5))
  done

  if [ $ELAPSED -ge $TIMEOUT ]; then
    fail "Services did not become healthy within ${TIMEOUT}s"
  fi

  # Hit key endpoints
  echo "→ Checking /health..."
  HTTP_CODE=$(curl -so /dev/null -w "%{http_code}" "$API_URL/health" 2>/dev/null || echo "000")
  if [ "$HTTP_CODE" = "200" ]; then
    pass "/health returns 200"
  else
    fail "/health returns $HTTP_CODE"
  fi

  echo "→ Checking /ready..."
  HTTP_CODE=$(curl -so /dev/null -w "%{http_code}" "$API_URL/ready" 2>/dev/null || echo "000")
  if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "503" ]; then
    pass "/ready returns $HTTP_CODE (acceptable)"
  else
    fail "/ready returns $HTTP_CODE"
  fi

  echo "→ Checking /metrics.json..."
  HTTP_CODE=$(curl -so /dev/null -w "%{http_code}" "$API_URL/metrics.json" 2>/dev/null || echo "000")
  if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "401" ] || [ "$HTTP_CODE" = "404" ]; then
    pass "/metrics.json returns $HTTP_CODE (expected)"
  else
    fail "/metrics.json returns $HTTP_CODE"
  fi

  # Cleanup
  info "Stopping and cleaning up..."
  docker compose -f docker-compose.yml -f docker-compose.prod.yml \
    --profile multi-worker --profile multi-shard down -v 2>&1 || true
  pass "Cleanup completed"
else
  info "Skipping full smoke test (run with --full flag for live service testing)"
fi

# -------------------------------------------
# Summary
# -------------------------------------------
echo ""
if [ "$FAILURES" -eq 0 ]; then
  echo -e "${GREEN}════════════════════════════════════════${NC}"
  if [ "$SKIPPED" -gt 0 ]; then
    echo -e "${GREEN}  ALL PRODUCTION SMOKE CHECKS PASSED ✅${NC}"
    echo -e "${YELLOW}  ($SKIPPED check(s) skipped — Docker not available)${NC}"
  else
    echo -e "${GREEN}  ALL PRODUCTION SMOKE CHECKS PASSED ✅${NC}"
  fi
  echo -e "${GREEN}════════════════════════════════════════${NC}"
  exit 0
else
  echo -e "${RED}════════════════════════════════════════${NC}"
  echo -e "${RED}  $FAILURES SMOKE CHECK(S) FAILED ❌${NC}"
  if [ "$SKIPPED" -gt 0 ]; then
    echo -e "${YELLOW}  ($SKIPPED check(s) skipped)${NC}"
  fi
  echo -e "${RED}════════════════════════════════════════${NC}"
  exit 1
fi
