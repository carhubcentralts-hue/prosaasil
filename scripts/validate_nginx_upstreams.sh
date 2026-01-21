#!/bin/bash
# ===========================================
# Validate Nginx Upstream Configuration
# ===========================================
# This script validates that nginx configuration references
# only service names that exist in docker-compose files.
# ===========================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🔍 Validating Nginx upstream configuration..."
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track if we found any issues
ISSUES_FOUND=0

# ===========================================
# 1. Check for legacy service names in nginx configs
# ===========================================
echo "📋 Checking for legacy service names in nginx configs..."

LEGACY_SERVICES=(
    "prosaas-api"
    "prosaas-calls"
)

for service in "${LEGACY_SERVICES[@]}"; do
    # Use proper regex for comments and better grep pattern
    if grep -r "$service" "$REPO_ROOT/docker/nginx/" 2>/dev/null | grep -v '^[[:space:]]*#' | grep -q "$service"; then
        echo -e "${RED}❌ ERROR: Found reference to legacy service '$service' in nginx configs${NC}"
        echo "   This service does not exist in docker-compose.yml (non-prod)"
        echo "   References found:"
        grep -rn "$service" "$REPO_ROOT/docker/nginx/" 2>/dev/null | grep -v '^[[:space:]]*#' | grep "$service" | sed 's/^/   /'
        ISSUES_FOUND=1
    else
        echo -e "${GREEN}✅ No references to legacy service '$service'${NC}"
    fi
done

echo ""

# ===========================================
# 2. Verify expected services are present
# ===========================================
echo "📋 Checking for expected service references..."

EXPECTED_SERVICES=(
    "prosaas-backend:5000"
    "prosaas-frontend:80"
    "prosaas-n8n:5678"
)

for service in "${EXPECTED_SERVICES[@]}"; do
    if grep -r "$service" "$REPO_ROOT/docker/nginx/" 2>/dev/null | grep -v "^\s*#" | grep -q "$service"; then
        echo -e "${GREEN}✅ Found expected service: $service${NC}"
    else
        echo -e "${YELLOW}⚠️  WARNING: Expected service '$service' not found in nginx configs${NC}"
    fi
done

echo ""

# ===========================================
# 3. Verify docker-compose services exist
# ===========================================
echo "📋 Verifying services exist in docker-compose.yml..."

# Check if prosaas-backend service exists (via backend service with container_name)
if grep -q "backend:" "$REPO_ROOT/docker-compose.yml" && \
   grep -q "container_name: prosaas-backend" "$REPO_ROOT/docker-compose.yml"; then
    echo -e "${GREEN}✅ Service 'backend' with container_name 'prosaas-backend' exists in docker-compose.yml${NC}"
else
    echo -e "${RED}❌ ERROR: Service 'backend' with container_name 'prosaas-backend' not found in docker-compose.yml${NC}"
    ISSUES_FOUND=1
fi

# Check if frontend service exists
if grep -q "frontend:" "$REPO_ROOT/docker-compose.yml" && \
   grep -q "container_name: prosaas-frontend" "$REPO_ROOT/docker-compose.yml"; then
    echo -e "${GREEN}✅ Service 'frontend' with container_name 'prosaas-frontend' exists in docker-compose.yml${NC}"
else
    echo -e "${RED}❌ ERROR: Service 'frontend' with container_name 'prosaas-frontend' not found in docker-compose.yml${NC}"
    ISSUES_FOUND=1
fi

echo ""

# ===========================================
# 4. Check server_name configuration
# ===========================================
echo "📋 Verifying server_name configuration..."

if grep -r "server_name prosaas.pro" "$REPO_ROOT/docker/nginx/" 2>/dev/null | grep -v "^\s*#" | grep -q "server_name prosaas.pro"; then
    echo -e "${GREEN}✅ Found 'server_name prosaas.pro' in nginx configs${NC}"
else
    echo -e "${RED}❌ ERROR: 'server_name prosaas.pro' not found in nginx configs${NC}"
    ISSUES_FOUND=1
fi

echo ""

# ===========================================
# Final Result
# ===========================================
if [ $ISSUES_FOUND -eq 0 ]; then
    echo -e "${GREEN}✅ All validation checks passed!${NC}"
    exit 0
else
    echo -e "${RED}❌ Validation failed! Please fix the issues above.${NC}"
    exit 1
fi
