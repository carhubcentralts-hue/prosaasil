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

# Run docker compose with both configuration files
docker compose --env-file .env \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  "$@"

# Validate no backend service after certain commands
validate_no_backend "$1"
