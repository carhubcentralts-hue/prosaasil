#!/usr/bin/env bash
# ===========================================
# ProSaaS Production Deployment Script
# Single source of truth for docker compose operations
# ===========================================
#
# Usage:
#   ./scripts/dcprod.sh ps
#   ./scripts/dcprod.sh up -d --build --force-recreate
#   ./scripts/dcprod.sh logs -f nginx
#   ./scripts/dcprod.sh logs --tail 80 worker
#
# This script ensures:
# - Always uses both docker-compose.yml and docker-compose.prod.yml
# - Always runs from repository root
# - Always uses .env file
# ===========================================

set -euo pipefail

# Navigate to repository root (one level up from scripts/)
cd "$(dirname "$0")/.."

# Verify required files exist
if [ ! -f .env ]; then
    echo "❌ ERROR: .env file not found in repository root"
    echo "Please create .env file before running deployment"
    exit 1
fi

if [ ! -f docker-compose.yml ]; then
    echo "❌ ERROR: docker-compose.yml not found in repository root"
    exit 1
fi

if [ ! -f docker-compose.prod.yml ]; then
    echo "❌ ERROR: docker-compose.prod.yml not found in repository root"
    exit 1
fi

# 🔥 PRODUCTION VALIDATION: Check if backend/legacy service is running after certain commands
validate_no_backend() {
    # Only validate after "up" or "ps" commands
    case "$1" in
        up|ps)
            # Check if backend service is running
            if docker compose --env-file .env \
              -f docker-compose.yml \
              -f docker-compose.prod.yml \
              ps --format json 2>/dev/null | grep -q '"Service":"backend"'; then
                echo "❌ ERROR: backend service is running in production!"
                echo "Production should use prosaas-api and prosaas-calls, not backend."
                echo ""
                echo "Current services:"
                docker compose --env-file .env \
                  -f docker-compose.yml \
                  -f docker-compose.prod.yml \
                  ps
                exit 1
            fi
            ;;
    esac
}

# 🔥 CRITICAL: After 'up' command, ensure backend is NOT running
# This prevents accidental backend deployment in production
check_backend_not_running() {
    if [ "$1" = "up" ]; then
        echo "⏳ Waiting for services to initialize..."
        sleep 5
        
        # 🔥 PRECISE CHECK: Use --services --filter status=running with exact word match
        backend_running=$(docker compose --env-file .env \
          -f docker-compose.yml \
          -f docker-compose.prod.yml \
          ps --services --filter "status=running" 2>/dev/null | grep -w "^backend$" | wc -l)
        
        if [ "$backend_running" -gt 0 ]; then
            echo ""
            echo "╔══════════════════════════════════════════════════════════════════════════════╗"
            echo "║                     ❌ DEPLOYMENT FAILED - BACKEND RUNNING ❌                ║"
            echo "╚══════════════════════════════════════════════════════════════════════════════╝"
            echo ""
            echo "ERROR: 'backend' service is running in production!"
            echo "Production architecture uses:"
            echo "  ✅ prosaas-api (HTTP API endpoints)"
            echo "  ✅ prosaas-calls (WebSocket + Twilio streaming)"
            echo "  ❌ backend (LEGACY - should NOT run)"
            echo ""
            echo "To fix:"
            echo "  1. Stop all services: ./scripts/dcprod.sh down"
            echo "  2. Ensure backend is under 'legacy' profile in docker-compose.prod.yml"
            echo "  3. Restart: ./scripts/dcprod.sh up -d"
            echo ""
            exit 1
        fi
        
        echo "✅ Backend service check passed (not running)"
    fi
}

# Run docker compose with both configuration files
docker compose --env-file .env \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  "$@"

# Validate no backend service after certain commands
validate_no_backend "$1"

# 🔥 CRITICAL: Hard-check backend is not running after 'up'
check_backend_not_running "$1"
