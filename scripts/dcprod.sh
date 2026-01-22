#!/usr/bin/env bash
# ==========================================
# ProSaaS Production Docker Compose Wrapper
# Single source of truth for deployment
# ==========================================
# 
# This script ensures:
# - No duplicate stacks (no -p flag, Docker determines name from directory)
# - No port conflicts (only nginx publishes ports 80/443)
# - Idempotent deployment (can run multiple times safely)
# - Consistent behavior (CI / manual / recovery)
# 
# Usage:
#   ./scripts/dcprod.sh down                    # Clean shutdown
#   ./scripts/dcprod.sh up -d --build          # Deploy with build
#   ./scripts/dcprod.sh up -d --force-recreate # Full recreate
#   ./scripts/dcprod.sh ps                      # Check status
#   ./scripts/dcprod.sh logs -f <service>       # View logs
# ==========================================

set -e

BASE_COMPOSE="docker-compose.yml"
PROD_COMPOSE="docker-compose.prod.yml"

if [[ ! -f "$BASE_COMPOSE" || ! -f "$PROD_COMPOSE" ]]; then
  echo "❌ docker-compose files not found"
  echo "   Expected: $BASE_COMPOSE and $PROD_COMPOSE"
  exit 1
fi

echo "🚀 ProSaaS Production Docker Compose"
echo "Using:"
echo " - $BASE_COMPOSE"
echo " - $PROD_COMPOSE"
echo ""

# Forward all args to docker compose
# ⚠️ CRITICAL: No -p flag! Docker determines project name from directory
# This prevents duplicate stacks (prosaas-* vs prosaasil-*)
docker compose \
  -f "$BASE_COMPOSE" \
  -f "$PROD_COMPOSE" \
  "$@"
