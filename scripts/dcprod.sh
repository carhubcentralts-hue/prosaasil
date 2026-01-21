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

# Verify .env file exists
if [ ! -f .env ]; then
    echo "❌ ERROR: .env file not found in repository root"
    echo "Please create .env file before running deployment"
    exit 1
fi

# Run docker compose with both configuration files
docker compose --env-file .env \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  "$@"
