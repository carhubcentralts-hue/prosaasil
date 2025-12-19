#!/bin/bash
# ===========================================
# Production API Verification - 5 Critical Curls
# Must run AFTER deployment to verify no 404s
# ===========================================

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default to production URL
BASE_URL="${1:-https://prosaas.pro}"

echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Production API Verification - 5 Critical Endpoints${NC}"
echo -e "${GREEN}Target: ${BASE_URL}${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Track results
FAILED=0
TOTAL=5

# Function to test endpoint
test_endpoint() {
    local path="$1"
    local name="$2"
    local url="${BASE_URL}${path}"
    
    echo -n "Testing ${name}... "
    
    # Get status code
    status=$(curl -s -o /dev/null -w "%{http_code}" "${url}" 2>/dev/null || echo "000")
    
    # Check status
    if [ "$status" = "200" ]; then
        echo -e "${GREEN}✅ ${status} OK${NC}"
        return 0
    elif [ "$status" = "401" ] || [ "$status" = "403" ]; then
        echo -e "${GREEN}✅ ${status} (endpoint exists, needs auth)${NC}"
        return 0
    elif [ "$status" = "404" ]; then
        echo -e "${RED}❌ 404 NOT FOUND${NC}"
        return 1
    elif [ "$status" = "000" ]; then
        echo -e "${RED}❌ CONNECTION FAILED${NC}"
        return 1
    else
        echo -e "${YELLOW}⚠️  ${status} (unexpected but not 404)${NC}"
        return 0
    fi
}

# Run the 5 critical tests
echo "Running 5 critical endpoint tests:"
echo "───────────────────────────────────────────────────────────"

if ! test_endpoint "/api/health" "Health"; then
    FAILED=$((FAILED + 1))
fi

if ! test_endpoint "/api/dashboard/stats?time_filter=today" "Dashboard Stats"; then
    FAILED=$((FAILED + 1))
fi

if ! test_endpoint "/api/dashboard/activity?time_filter=today" "Dashboard Activity"; then
    FAILED=$((FAILED + 1))
fi

if ! test_endpoint "/api/business/current" "Business Current"; then
    FAILED=$((FAILED + 1))
fi

if ! test_endpoint "/api/whatsapp/status" "WhatsApp Status"; then
    FAILED=$((FAILED + 1))
fi

# Summary
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Results: $((TOTAL - FAILED))/${TOTAL} tests passed${NC}"

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ ALL CRITICAL ENDPOINTS WORKING${NC}"
    echo -e "${GREEN}   No 404 errors detected!${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
    exit 0
else
    echo -e "${RED}❌ FAILED: ${FAILED} endpoint(s) returning 404${NC}"
    echo ""
    echo -e "${YELLOW}This means critical API routes are not registered!${NC}"
    echo -e "${YELLOW}Check backend logs for blueprint registration errors:${NC}"
    echo "  docker logs prosaas-backend | grep -i 'critical\|error\|blueprint'"
    echo ""
    echo -e "${YELLOW}Check route registration:${NC}"
    echo "  curl ${BASE_URL}/api/debug/routes | jq '.critical_endpoints'"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
    exit 1
fi
