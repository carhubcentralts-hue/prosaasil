#!/usr/bin/env bash
# ===========================================
# ProSaaS Quality Gate — Single Source of Truth
# ===========================================
# All CI checks funnel through this script.
# Exit code: 0 = all gates passed, non-zero = failure.
#
# Usage:
#   ./scripts/quality_gate.sh          # Run all gates
#   ./scripts/quality_gate.sh client   # Run client gates only
#   ./scripts/quality_gate.sh server   # Run server gates only
#   ./scripts/quality_gate.sh e2e      # Run e2e gates only
# ===========================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

FAILURES=0
TARGET="${1:-all}"

pass() { echo -e "${GREEN}✅ PASS${NC}: $1"; }
fail() { echo -e "${RED}❌ FAIL${NC}: $1"; FAILURES=$((FAILURES + 1)); }
info() { echo -e "${YELLOW}ℹ️  INFO${NC}: $1"; }

# -------------------------------------------
# Client (Frontend) Quality Gates
# -------------------------------------------
run_client() {
  info "=== Client Quality Gates ==="

  echo "→ ESLint..."
  if (cd client && npm run lint); then
    pass "ESLint"
  else
    fail "ESLint"
  fi

  echo "→ TypeScript typecheck..."
  if (cd client && npm run typecheck 2>/dev/null || npm run check 2>/dev/null); then
    pass "TypeScript typecheck"
  else
    fail "TypeScript typecheck"
  fi

  echo "→ Vitest unit tests..."
  if (cd client && npm run test -- --run 2>/dev/null || npm test 2>/dev/null); then
    pass "Vitest unit tests"
  else
    fail "Vitest unit tests"
  fi

  echo "→ Production build..."
  if (cd client && npm run build -- --mode production); then
    pass "Production build"
  else
    fail "Production build"
  fi

  echo "→ npm audit (high/critical)..."
  if (cd client && npm audit --omit=dev --audit-level=high); then
    pass "npm audit"
  else
    fail "npm audit — see client/AUDIT_ALLOWLIST.md for known exceptions"
  fi

  echo "→ No sourcemaps in dist..."
  if ! find client/dist -name "*.map" 2>/dev/null | grep -q .; then
    pass "No sourcemaps in production build"
  else
    fail "Sourcemap files found in production build"
  fi
}

# -------------------------------------------
# Server (Backend) Quality Gates
# -------------------------------------------
run_server() {
  info "=== Server Quality Gates ==="

  echo "→ Ruff lint..."
  if ruff check server/ 2>/dev/null; then
    pass "Ruff lint"
  else
    fail "Ruff lint"
  fi

  echo "→ pytest unit tests..."
  if pytest tests/test_appointment_reminder_weekday_fix.py \
           tests/test_business_settings_cache.py \
           tests/test_cors_recording_playback.py \
           tests/test_export_leads_by_status.py \
           tests/test_hebrew_datetime_year_correction.py \
           tests/test_scheduled_messages_first_name.py \
           tests/test_webhook_payload.py \
           -v --tb=short 2>/dev/null; then
    pass "pytest unit tests"
  else
    fail "pytest unit tests"
  fi

  echo "→ pip-audit security..."
  if [ -f requirements.lock ]; then
    if pip-audit --desc --requirement requirements.lock 2>/dev/null; then
      pass "pip-audit security (from requirements.lock)"
    else
      fail "pip-audit security — see server/AUDIT_ALLOWLIST.md for known exceptions"
    fi
  elif pip-audit --desc --requirement <(pip freeze) 2>/dev/null; then
    pass "pip-audit security"
  else
    fail "pip-audit security — see server/AUDIT_ALLOWLIST.md for known exceptions"
  fi
}

# -------------------------------------------
# E2E Quality Gates
# -------------------------------------------
run_e2e() {
  info "=== E2E Quality Gates ==="

  echo "→ Playwright e2e tests..."
  if npx playwright test 2>/dev/null; then
    pass "Playwright e2e tests"
  else
    fail "Playwright e2e tests"
  fi
}

# -------------------------------------------
# Docker Validation
# -------------------------------------------
run_docker() {
  info "=== Docker Quality Gates ==="

  echo "→ docker-compose config validation..."
  if docker compose -f docker-compose.yml -f docker-compose.prod.yml config > /dev/null 2>&1; then
    pass "docker-compose config"
  else
    fail "docker-compose config"
  fi
}

# -------------------------------------------
# Main
# -------------------------------------------
case "$TARGET" in
  client)  run_client ;;
  server)  run_server ;;
  e2e)     run_e2e ;;
  docker)  run_docker ;;
  all)
    run_client
    run_server
    run_docker
    # E2E requires running services, skip in basic gate
    info "E2E tests skipped in 'all' mode (requires running services). Run: ./scripts/quality_gate.sh e2e"
    ;;
  *)
    echo "Usage: $0 {all|client|server|e2e|docker}"
    exit 1
    ;;
esac

echo ""
if [ "$FAILURES" -eq 0 ]; then
  echo -e "${GREEN}════════════════════════════════════════${NC}"
  echo -e "${GREEN}  ALL QUALITY GATES PASSED ✅${NC}"
  echo -e "${GREEN}════════════════════════════════════════${NC}"
  exit 0
else
  echo -e "${RED}════════════════════════════════════════${NC}"
  echo -e "${RED}  $FAILURES QUALITY GATE(S) FAILED ❌${NC}"
  echo -e "${RED}════════════════════════════════════════${NC}"
  exit 1
fi
